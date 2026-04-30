"""Voice Live session service — adjuster copilot WebSocket sessions.

Creates and manages Voice Live sessions for the adjuster copilot.
Handles session config generation, tool binding, and WebSocket relay.

Uses Azure Voice Live API (preview) with:
- Semantic VAD (azure_semantic_vad) for turn detection
- Inline or MCP tool definitions for claim lookup
- PCM16 audio format for browser streaming
- Optional avatar config for customer-facing bot (future)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from backend.core.config import get_settings
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
        """Create a new adjuster voice session for a processed claim.

        Args:
            claim_id: The claim to discuss in the session.
            adjuster_id: Identifier for the adjuster.

        Returns:
            Session metadata with WebSocket URL and auth token.

        Raises:
            ValueError: If the claim is not found or not processed.
        """
        # Validate claim exists and has data
        claim_result = self._lookup.get_claim_summary(claim_id)
        if not claim_result.found:
            raise ValueError(f"Claim {claim_id} not found")

        settings = get_settings()
        session_id = uuid.uuid4().hex[:16]
        token = self._generate_session_token(session_id, claim_id, adjuster_id)

        ws_url = ""
        if settings.voice_live_endpoint:
            ws_url = (
                f"wss://{settings.voice_live_endpoint.replace('https://', '').replace('http://', '')}"
                f"/voice/live?api-version={settings.voice_live_api_version}"
                f"&session_id={session_id}"
            )

        return AdjusterSessionResponse(
            session_id=session_id,
            claim_id=claim_id,
            ws_url=ws_url,
            token=token,
            status=SessionStatus.CONNECTING,
        )

    def build_session_config(self, claim_id: str) -> VoiceLiveSessionConfig:
        """Build the Voice Live session configuration.

        Includes adjuster copilot instructions, claim lookup tools,
        and optional MCP server binding.
        """
        settings = get_settings()

        # Build instructions with claim context
        claim_summary = self._lookup.get_claim_summary(claim_id)
        instructions = ADJUSTER_SYSTEM_INSTRUCTIONS
        if claim_summary.found:
            instructions += f"\n\nCurrent claim context: {claim_summary.summary}"

        config = VoiceLiveSessionConfig(
            voice=settings.voice_live_voice,
            instructions=instructions,
        )

        # Add tools (inline or MCP)
        if settings.voice_live_enable_mcp and settings.voice_live_mcp_server_url:
            mcp_config = self._mcp.get_mcp_server_config(settings.voice_live_mcp_server_url)
            config.mcp_servers = mcp_config.get("mcp_servers", [])
        else:
            inline_config = self._mcp.get_inline_config()
            config.tools = inline_config.get("tools", [])

        return config

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Handle a tool call from the Voice Live session.

        Dispatches to the MCP adapter which routes to ClaimLookupTool.
        """
        return self._mcp.handle_tool_call(tool_name, arguments)

    def process_voice_event(self, event_data: dict[str, Any]) -> VoiceLiveEvent | None:
        """Process an incoming Voice Live event and return response events.

        Handles tool_call events by dispatching to ClaimLookupTool.
        Passes through all other events.
        """
        event_type_str = event_data.get("type", "")

        # Handle tool calls from Voice Live
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

        # Pass through transcript events
        if "transcript" in event_type_str:
            return VoiceLiveEvent(
                event_type=VoiceLiveEventType.TRANSCRIPT,
                data=event_data,
            )

        return None

    def _generate_session_token(
        self, session_id: str, claim_id: str, adjuster_id: str
    ) -> str:
        """Generate a deterministic token for local dev.

        In production, this would use JWT with ADJUSTER_SESSION_TOKEN_SECRET.
        """
        settings = get_settings()
        raw = f"{session_id}:{claim_id}:{adjuster_id}:{settings.adjuster_session_token_secret}"
        return f"cp-{uuid.uuid5(uuid.NAMESPACE_URL, raw).hex}"

    def get_avatar_config(self) -> AvatarConfig:
        """Return default avatar config. Avatar is not enabled in Phase 4."""
        return AvatarConfig()
