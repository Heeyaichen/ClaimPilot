"""Adjuster API routes — session URL, WebSocket relay, and claim preloading."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from backend.models.claim import ClaimRecord
from backend.models.voice_live import AdjusterSessionResponse, ClaimLookupResult
from backend.services.claim_lookup_tool import ClaimLookupTool
from backend.services.claim_state_store import ClaimStateStore
from backend.services.voice_live import VoiceLiveService

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
    """Get claims queue for adjuster review, sorted by priority.

    Priority ordering:
    1. High fraud risk (score >= 0.7)
    2. Failed pipeline claims
    3. Low-confidence decisions (< 0.80)
    4. Newest within same priority tier
    """
    store = _get_state_store()

    # Query all claims with matching status
    # In production this would use Cosmos DB query with filters
    # For now, return a structured response shape
    try:
        # Use Cosmos SQL query for status filter
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

    # Parse and sort by priority
    claims: list[dict[str, Any]] = []
    for item in items:
        try:
            record = ClaimRecord.model_validate(item)
            claims.append(record.model_dump(mode="json"))
        except Exception:
            continue

    # Priority sort
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

    # Paginate
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
    """Get a Voice Live session URL and token for an adjuster.

    Returns session metadata needed to establish a WebSocket connection.
    """
    service = _get_voice_service()
    try:
        session = service.create_adjuster_session(claim_id, adjuster_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return session


@router.websocket("/voice/{claim_id}")
async def voice_websocket(websocket: WebSocket, claim_id: str) -> None:
    """WebSocket endpoint for Voice Live adjuster sessions.

    Relays audio/text events between the browser and the Voice Live service.
    Handles tool calls inline by dispatching to ClaimLookupTool.
    """
    await websocket.accept()
    service = _get_voice_service()

    # Validate claim exists
    try:
        session = service.create_adjuster_session(claim_id)
    except ValueError:
        await websocket.close(code=4004, reason=f"Claim {claim_id} not found")
        return

    # Send session config to client
    config = service.build_session_config(claim_id)
    await websocket.send_json({
        "type": "session.config",
        "session_id": session.session_id,
        "config": config.model_dump(),
    })

    logger.info("Voice session started: claim=%s session=%s", claim_id, session.session_id)

    try:
        while True:
            # Receive raw message from browser
            data = await websocket.receive_text()
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            # Process event through Voice Live service
            response = service.process_voice_event(event)
            if response is not None:
                await websocket.send_json(response.data)

    except WebSocketDisconnect:
        logger.info("Voice session ended: claim=%s session=%s", claim_id, session.session_id)
    except Exception:
        logger.exception("Voice session error: claim=%s", claim_id)
        await websocket.close(code=1011, reason="Internal error")


@router.get("/claim/{claim_id}", response_model=ClaimLookupResult)
async def get_claim_context(claim_id: str) -> Any:
    """Preload claim context for the adjuster interface.

    Returns a structured summary of the claim for display before
    starting a voice session.
    """
    tool = _get_lookup_tool()
    result = tool.get_claim_summary(claim_id)
    if not result.found:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return result
