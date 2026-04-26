"""Voice Live models — session config, events, avatar, and adjuster API shapes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    """Voice Live session lifecycle."""

    CONNECTING = "CONNECTING"
    ACTIVE = "ACTIVE"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class VoiceLiveEventType(StrEnum):
    """Event types flowing through the Voice Live WebSocket."""

    SESSION_CREATED = "session.created"
    AUDIO_INPUT = "audio.input"
    AUDIO_OUTPUT = "audio.output"
    TRANSCRIPT = "transcript"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    SESSION_ENDED = "session.ended"


# --- Request / Response models ---


class AdjusterSessionRequest(BaseModel):
    """Request to start an adjuster voice session."""

    claim_id: str
    adjuster_id: str = "default-adjuster"


class AdjusterSessionResponse(BaseModel):
    """Response with session metadata and connection details."""

    session_id: str
    claim_id: str
    ws_url: str
    token: str
    status: SessionStatus = SessionStatus.CONNECTING
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceLiveSessionConfig(BaseModel):
    """Configuration sent to Voice Live API when creating a session."""

    modalities: list[str] = Field(default=["text", "audio"])
    voice: str = "en-US-AvaMultilingualNeural"
    input_audio_format: str = "pcm16"
    output_audio_format: str = "pcm16"
    turn_detection: dict[str, Any] = Field(
        default_factory=lambda: {"type": "azure_semantic_vad"},
    )
    instructions: str = ""
    tools: list[dict[str, Any]] = Field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)


class VoiceLiveEvent(BaseModel):
    """Generic event from the Voice Live WebSocket."""

    event_type: VoiceLiveEventType
    session_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict[str, Any] = Field(default_factory=dict)


class VoiceLiveTranscriptEvent(BaseModel):
    """Transcript event from voice interaction."""

    role: str  # "user" | "assistant"
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ClaimLookupResult(BaseModel):
    """Structured result from a claim lookup tool call."""

    claim_id: str
    found: bool
    summary: str = ""
    fraud_score: float | None = None
    decision: str | None = None
    approved_amount: float | None = None
    damage_assessment: str | None = None
    reasoning_summary: str | None = None
    error: str | None = None


class AvatarConfig(BaseModel):
    """Photo avatar configuration for customer-facing bot (future)."""

    enabled: bool = False
    character: str = "standard"
    sdp_offer: str | None = None
    sdp_answer: str | None = None
    webrtc_enabled: bool = False
