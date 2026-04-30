"""Adjuster API routes — session URL, WebSocket relay, and claim preloading."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from backend.core.config import get_settings
from backend.models.claim import ClaimRecord
from backend.models.voice_live import AdjusterSessionResponse, ClaimLookupResult
from backend.services.claim_lookup_tool import ClaimLookupTool
from backend.services.claim_state_store import ClaimStateStore
from backend.services.voice_live import VoiceLiveBridge, VoiceLiveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/adjuster", tags=["adjuster"])


def _get_voice_service() -> VoiceLiveService:
    return VoiceLiveService()


def _get_lookup_tool() -> ClaimLookupTool:
    return ClaimLookupTool(state_store=ClaimStateStore())


def _get_state_store() -> ClaimStateStore:
    return ClaimStateStore()


@router.get("/queue")
async def get_adjuster_queue(
    status: str = Query("ESCALATED", description="Filter by claim status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> Any:
    """Get claims queue for adjuster review, sorted by priority."""
    store = _get_state_store()

    try:
        container = store._get_container()
        query = "SELECT * FROM c WHERE c.status = @status ORDER BY c.updated_at DESC"
        params = [{"name": "@status", "value": status}]
        items = list(container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
        ))
    except Exception:
        logger.warning("Failed to query adjuster queue from Cosmos DB")
        items = []

    claims: list[dict[str, Any]] = []
    for item in items:
        try:
            record = ClaimRecord.model_validate(item)
            claims.append(record.model_dump(mode="json"))
        except Exception:
            continue

    def _priority_key(claim: dict[str, Any]) -> tuple[int, str]:
        fraud_score = 0.0
        fraud_result = claim.get("fraud_result")
        if fraud_result and isinstance(fraud_result, dict):
            fraud_score = fraud_result.get("score", 0.0)

        if claim.get("status") == "FAILED":
            tier = 0
        elif fraud_score >= 0.7:
            tier = 1
        elif fraud_score >= 0.4:
            tier = 2
        else:
            tier = 3

        updated = claim.get("updated_at", "")
        return (tier, updated)

    claims.sort(key=_priority_key)

    start = (page - 1) * page_size
    paginated = claims[start : start + page_size]

    return {
        "claims": paginated,
        "total": len(claims),
        "page": page,
        "page_size": page_size,
    }


@router.get("/session-url", response_model=AdjusterSessionResponse)
async def get_session_url(
    claim_id: str = Query(..., description="Claim ID to start session for"),
    adjuster_id: str = Query("default-adjuster", description="Adjuster identifier"),
) -> Any:
    """Get a Voice Live session URL and token for an adjuster."""
    service = _get_voice_service()
    try:
        session = service.create_adjuster_session(claim_id, adjuster_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return session


@router.websocket("/voice/{claim_id}")
async def voice_websocket(websocket: WebSocket, claim_id: str) -> None:
    """WebSocket endpoint for Voice Live adjuster sessions.

    When Voice Live is configured, acts as a bidirectional relay between
    the browser and Azure Voice Live. Falls back to text-only mode otherwise.
    """
    await websocket.accept()

    settings = get_settings()
    voice_live_configured = bool(settings.voice_live_endpoint)

    # Validate claim exists
    lookup = _get_lookup_tool()
    claim_result = lookup.get_claim_summary(claim_id)
    if not claim_result.found:
        await websocket.close(code=4004, reason=f"Claim {claim_id} not found")
        return

    # Try to connect to Voice Live
    bridge: VoiceLiveBridge | None = None
    voice_live_available = False

    if voice_live_configured:
        try:
            bridge = VoiceLiveBridge(claim_id, lookup)
            await bridge.connect(settings)
            voice_live_available = True
        except Exception:
            logger.warning(
                "Voice Live connect failed for claim=%s, using text fallback",
                claim_id, exc_info=True,
            )
            bridge = None

    # Send session config to browser
    if voice_live_available and bridge is not None:
        await websocket.send_json({
            "type": "session.config",
            "session_id": bridge.session_id,
            "mode": "voice_live",
            "audio_enabled": True,
            "text_fallback_enabled": True,
        })
        logger.info("Voice Live session started: claim=%s session=%s", claim_id, bridge.session_id)
    else:
        await websocket.send_json({
            "type": "session.config",
            "session_id": "text-fallback",
            "mode": "text_fallback",
            "audio_enabled": False,
            "text_fallback_enabled": True,
            "warning": "Voice Live is not configured; text fallback is active.",
        })
        logger.info("Text fallback session started: claim=%s", claim_id)

    # Enter appropriate loop
    if voice_live_available and bridge is not None:
        await _voice_live_relay(websocket, bridge, claim_id)
    else:
        await _text_fallback_loop(websocket, claim_id)


async def _voice_live_relay(
    websocket: WebSocket, bridge: VoiceLiveBridge, claim_id: str,
) -> None:
    """Bidirectional relay between browser and Azure Voice Live."""
    stop = asyncio.Event()

    async def browser_to_vl() -> None:
        """Forward browser messages to Voice Live."""
        while not stop.is_set():
            try:
                message = await websocket.receive()
            except Exception:
                stop.set()
                break

            if "bytes" in message:
                await bridge.send_audio(message["bytes"])
                continue

            text = message.get("text", "")
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "text.input":
                await bridge.send_text(event.get("text", ""))

    async def vl_to_browser() -> None:
        """Forward Voice Live events to browser, handle tool calls."""
        while not stop.is_set():
            try:
                event = await bridge.recv_event()
            except websockets.ConnectionClosed:
                break
            except Exception:
                logger.exception("Voice Live recv error: claim=%s", claim_id)
                break

            event_type = event.get("type", "")

            # Handle function calls locally
            if event_type == "response.function_call_arguments.done":
                try:
                    await bridge.handle_function_call(event)
                except Exception:
                    logger.exception("Tool call error: claim=%s", claim_id)
                continue

            # Forward everything else to browser
            try:
                await websocket.send_json(event)
            except Exception:
                stop.set()
                break

    task_b2v = asyncio.create_task(browser_to_vl())
    task_v2b = asyncio.create_task(vl_to_browser())

    try:
        done, _ = await asyncio.wait(
            [task_b2v, task_v2b],
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for t in done:
            if t.exception() and not isinstance(t.exception(), (WebSocketDisconnect, websockets.ConnectionClosed)):
                logger.exception("Relay task error: claim=%s", claim_id)
    except WebSocketDisconnect:
        logger.info("Browser disconnected from Voice Live: claim=%s", claim_id)
    except Exception:
        logger.exception("Voice Live relay error: claim=%s", claim_id)
    finally:
        stop.set()
        task_b2v.cancel()
        task_v2b.cancel()
        await bridge.close()


async def _text_fallback_loop(websocket: WebSocket, claim_id: str) -> None:
    """Text-only fallback loop for when Voice Live is unavailable."""
    audio_warned = False
    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                if not audio_warned:
                    audio_warned = True
                    await websocket.send_json({
                        "type": "warning",
                        "message": "Audio streaming unavailable; use text fallback.",
                    })
                continue

            text = message.get("text", "")
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "recoverable": True,
                    "message": "Invalid JSON",
                })
                continue

            if event.get("type") == "text.input":
                await _handle_text_fallback(websocket, claim_id, event.get("text", ""))

    except WebSocketDisconnect:
        logger.info("Text fallback session ended: claim=%s", claim_id)
    except Exception:
        logger.exception("Text fallback error: claim=%s", claim_id)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass


async def _handle_text_fallback(websocket: WebSocket, claim_id: str, text: str) -> None:
    """Handle a text input message in fallback mode by querying claim tools."""
    lookup = _get_lookup_tool()
    text_lower = text.lower()

    try:
        if "fraud" in text_lower or "risk" in text_lower:
            result = lookup.get_fraud_score(claim_id)
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": f"Fraud Score: {result.summary}",
            })
        elif "damage" in text_lower or "assessment" in text_lower or "repair" in text_lower:
            result = lookup.get_damage_assessment(claim_id)
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": f"Damage Assessment: {result.summary}",
            })
        elif "decision" in text_lower or "reason" in text_lower or "why" in text_lower:
            result = lookup.get_decision_reasoning(claim_id)
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": f"Decision Reasoning: {result.summary}",
            })
        else:
            result = lookup.get_claim_summary(claim_id)
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": f"Claim Summary: {result.summary}",
            })
    except Exception:
        logger.exception("Text fallback lookup failed: claim=%s", claim_id)
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to look up claim data: {text[:100]}",
        })


@router.get("/claim/{claim_id}", response_model=ClaimLookupResult)
async def get_claim_context(claim_id: str) -> Any:
    """Preload claim context for the adjuster interface."""
    tool = _get_lookup_tool()
    result = tool.get_claim_summary(claim_id)
    if not result.found:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return result
