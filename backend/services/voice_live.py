"""Voice Live session service — adjuster copilot WebSocket sessions.

Creates and manages Voice Live sessions for the adjuster copilot.
Handles session config generation, tool binding, and WebSocket relay.

Uses Azure Voice Live API with:
- Semantic VAD (azure_semantic_vad) for turn detection
- Inline tool definitions for claim lookup
- PCM16 audio format for browser streaming
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

import websockets

from backend.core.config import Settings, get_settings
from backend.mcp.claim_server import MCPClaimServerAdapter
from backend.models.voice_live import (
    AdjusterSessionResponse,
    AvatarConfig,
    SessionStatus,
    VoiceLiveEvent,
    VoiceLiveEventType,
    VoiceLiveSessionConfig,
)
from backend.services.claim_lookup_tool import (
    ADJUSTER_SYSTEM_INSTRUCTIONS,
    ClaimLookupTool,
)
from backend.services.claim_state_store import ClaimStateStore

logger = logging.getLogger(__name__)


class VoiceLiveBridge:
    """Bidirectional WebSocket relay between browser and Azure Voice Live.

    Connects to the Azure Voice Live realtime endpoint and relays:
    - Browser PCM16 audio → Voice Live (base64-encoded)
    - Browser text → Voice Live conversation items
    - Voice Live responses → Browser (transcript, audio, tool results)
    - Voice Live function calls → ClaimLookupTool → Voice Live output
    """

    def __init__(self, claim_id: str, lookup: ClaimLookupTool) -> None:
        self._claim_id = claim_id
        self._lookup = lookup
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._session_id: str = ""

    async def connect(self, settings: Settings) -> str:
        """Connect to Voice Live WebSocket and configure session.

        Returns the Voice Live session ID.

        Raises:
            Exception: If connection or session setup fails.
        """
        from azure.identity import DefaultAzureCredential

        # Get auth token
        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        headers = {"Authorization": f"Bearer {token.token}"}

        # Build Voice Live WebSocket URL
        endpoint = settings.voice_live_endpoint.rstrip("/")
        ws_host = endpoint.replace("https://", "wss://").replace("http://", "ws://")
        # Try services.ai.azure.com domain for Voice Live
        ws_host = ws_host.replace(".cognitiveservices.azure.com", ".services.ai.azure.com")
        url = (
            f"{ws_host}/voice-live/realtime"
            f"?api-version={settings.voice_live_api_version}"
            f"&model={settings.voice_live_model}"
        )

        logger.info("Connecting to Voice Live: %s", url.split("?")[0])

        self._ws = await websockets.connect(url, additional_headers=headers)

        # Wait for session.created
        event = json.loads(await self._ws.recv())
        if event.get("type") != "session.created":
            raise RuntimeError(f"Expected session.created, got: {event.get('type')}")
        self._session_id = event.get("session", {}).get("id", "unknown")

        # Build and send session config
        claim_summary = self._lookup.get_claim_summary(self._claim_id)
        instructions = ADJUSTER_SYSTEM_INSTRUCTIONS
        if claim_summary.found:
            instructions += f"\n\nCurrent claim context: {claim_summary.summary}"

        # Build tool definitions in Voice Live format (flat, not nested)
        raw_tools = self._lookup.as_tool_definitions()
        vl_tools = []
        for t in raw_tools:
            fn = t.get("function", {})
            vl_tools.append({
                "type": "function",
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })

        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": settings.voice_live_voice,
                "instructions": instructions,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "azure_semantic_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
                "input_audio_transcription": {
                    "model": settings.voice_live_transcription_model,
                    "language": settings.voice_live_transcription_language,
                },
                "tools": vl_tools,
            },
        }
        await self._ws.send(json.dumps(config))

        # Wait for session.updated
        event = json.loads(await self._ws.recv())
        if event.get("type") == "error":
            error_msg = event.get("error", {}).get("message", str(event))
            raise RuntimeError(f"Voice Live session config error: {error_msg}")
        if event.get("type") != "session.updated":
            raise RuntimeError(f"Expected session.updated, got: {event.get('type')}")

        logger.info("Voice Live session ready: %s", self._session_id)
        return self._session_id

    async def send_audio(self, pcm16_bytes: bytes) -> None:
        """Forward PCM16 audio to Voice Live (base64-encoded)."""
        if not self._ws:
            return
        b64 = base64.b64encode(pcm16_bytes).decode("ascii")
        await self._ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": b64,
        }))

    async def send_text(self, text: str) -> None:
        """Forward text input to Voice Live."""
        if not self._ws:
            return
        await self._ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }))
        await self._ws.send(json.dumps({"type": "response.create"}))

    async def recv_event(self) -> dict[str, Any]:
        """Receive next event from Voice Live."""
        if not self._ws:
            raise RuntimeError("Voice Live not connected")
        data = await self._ws.recv()
        return json.loads(data)

    async def handle_function_call(self, event: dict[str, Any]) -> None:
        """Handle a function call from Voice Live and send result back."""
        name = event.get("name", "")
        call_id = event.get("call_id", "")
        try:
            arguments = json.loads(event.get("arguments", "{}"))
        except json.JSONDecodeError:
            arguments = {}

        result = self._lookup.handle_tool_call(name, arguments)
        result_str = json.dumps(result.model_dump())

        await self._ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result_str,
            },
        }))
        logger.info("Tool call handled: %s for claim=%s", name, self._claim_id)

    async def close(self) -> None:
        """Close the Voice Live WebSocket."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    @property
    def session_id(self) -> str:
        return self._session_id


class VoiceLiveService:
    """Manages Voice Live sessions for the adjuster voice copilot."""

    def __init__(
        self,
        claim_lookup: ClaimLookupTool | None = None,
        mcp_adapter: MCPClaimServerAdapter | None = None,
    ) -> None:
        self._lookup = claim_lookup or ClaimLookupTool(state_store=ClaimStateStore())
        self._mcp = mcp_adapter or MCPClaimServerAdapter(lookup_tool=self._lookup)

    def create_adjuster_session(
        self,
        claim_id: str,
        adjuster_id: str = "default-adjuster",
    ) -> AdjusterSessionResponse:
        """Create a new adjuster voice session for a processed claim."""
        claim_result = self._lookup.get_claim_summary(claim_id)
        if not claim_result.found:
            raise ValueError(f"Claim {claim_id} not found")

        session_id = uuid.uuid4().hex[:16]
        token = self._generate_session_token(session_id, claim_id, adjuster_id)

        return AdjusterSessionResponse(
            session_id=session_id,
            claim_id=claim_id,
            ws_url="",
            token=token,
            status=SessionStatus.CONNECTING,
        )

    def build_session_config(self, claim_id: str) -> VoiceLiveSessionConfig:
        """Build the Voice Live session configuration."""
        settings = get_settings()

        claim_summary = self._lookup.get_claim_summary(claim_id)
        instructions = ADJUSTER_SYSTEM_INSTRUCTIONS
        if claim_summary.found:
            instructions += f"\n\nCurrent claim context: {claim_summary.summary}"

        config = VoiceLiveSessionConfig(
            voice=settings.voice_live_voice,
            instructions=instructions,
        )

        if settings.voice_live_enable_mcp and settings.voice_live_mcp_server_url:
            mcp_config = self._mcp.get_mcp_server_config(settings.voice_live_mcp_server_url)
            config.mcp_servers = mcp_config.get("mcp_servers", [])
        else:
            inline_config = self._mcp.get_inline_config()
            config.tools = inline_config.get("tools", [])

        return config

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Handle a tool call from the Voice Live session."""
        return self._mcp.handle_tool_call(tool_name, arguments)

    def process_voice_event(self, event_data: dict[str, Any]) -> VoiceLiveEvent | None:
        """Process an incoming Voice Live event and return response events."""
        event_type_str = event_data.get("type", "")

        if event_type_str == "response.function_call_arguments.done":
            tool_name = event_data.get("name", "")
            call_id = event_data.get("call_id", "")
            try:
                arguments = json.loads(event_data.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            result_str = self.handle_tool_call(tool_name, arguments)

            return VoiceLiveEvent(
                event_type=VoiceLiveEventType.TOOL_RESULT,
                data={
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result_str,
                    },
                },
            )

        if "transcript" in event_type_str:
            return VoiceLiveEvent(
                event_type=VoiceLiveEventType.TRANSCRIPT,
                data=event_data,
            )

        return None

    def _generate_session_token(
        self, session_id: str, claim_id: str, adjuster_id: str
    ) -> str:
        """Generate a deterministic token for local dev."""
        settings = get_settings()
        raw = f"{session_id}:{claim_id}:{adjuster_id}:{settings.adjuster_session_token_secret}"
        return f"cp-{uuid.uuid5(uuid.NAMESPACE_URL, raw).hex}"

    def get_avatar_config(self) -> AvatarConfig:
        """Return default avatar config. Avatar is not enabled in Phase 4."""
        return AvatarConfig()
