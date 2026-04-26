"""Unit tests for Voice Live models."""

from datetime import datetime

from backend.models.voice_live import (
    AdjusterSessionResponse,
    AvatarConfig,
    ClaimLookupResult,
    SessionStatus,
    VoiceLiveEvent,
    VoiceLiveEventType,
    VoiceLiveSessionConfig,
    VoiceLiveTranscriptEvent,
)


def test_session_status_values():
    assert SessionStatus.CONNECTING == "CONNECTING"
    assert SessionStatus.ACTIVE == "ACTIVE"
    assert SessionStatus.DISCONNECTED == "DISCONNECTED"
    assert SessionStatus.ERROR == "ERROR"


def test_voice_live_event_type_values():
    assert VoiceLiveEventType.SESSION_CREATED == "session.created"
    assert VoiceLiveEventType.TOOL_CALL == "tool_call"
    assert VoiceLiveEventType.TOOL_RESULT == "tool_result"
    assert VoiceLiveEventType.TRANSCRIPT == "transcript"


def test_adjuster_session_response():
    resp = AdjusterSessionResponse(
        session_id="abc123",
        claim_id="claim1",
        ws_url="wss://example.com/voice",
        token="cp-test-token",
    )
    assert resp.status == SessionStatus.CONNECTING
    assert resp.session_id == "abc123"
    assert isinstance(resp.created_at, datetime)


def test_voice_live_session_config_defaults():
    config = VoiceLiveSessionConfig()
    assert "text" in config.modalities
    assert "audio" in config.modalities
    assert config.turn_detection["type"] == "azure_semantic_vad"
    assert config.input_audio_format == "pcm16"
    assert config.output_audio_format == "pcm16"


def test_voice_live_session_config_custom():
    config = VoiceLiveSessionConfig(
        voice="en-US-JennyNeural",
        instructions="Test instructions",
        tools=[{"type": "function", "function": {"name": "test"}}],
    )
    assert config.voice == "en-US-JennyNeural"
    assert len(config.tools) == 1


def test_voice_live_event():
    event = VoiceLiveEvent(
        event_type=VoiceLiveEventType.TRANSCRIPT,
        session_id="s1",
        data={"role": "user", "text": "Hello"},
    )
    assert event.event_type == VoiceLiveEventType.TRANSCRIPT
    assert event.data["text"] == "Hello"


def test_voice_live_transcript_event():
    event = VoiceLiveTranscriptEvent(role="user", text="What is the fraud score?")
    assert event.role == "user"
    assert event.text == "What is the fraud score?"


def test_claim_lookup_result_found():
    result = ClaimLookupResult(
        claim_id="c1",
        found=True,
        summary="Test claim",
        fraud_score=0.25,
        decision="APPROVE",
    )
    assert result.found is True
    assert result.fraud_score == 0.25


def test_claim_lookup_result_not_found():
    result = ClaimLookupResult(
        claim_id="c1",
        found=False,
        error="Claim not found",
    )
    assert result.found is False
    assert result.error == "Claim not found"


def test_avatar_config_defaults():
    config = AvatarConfig()
    assert config.enabled is False
    assert config.character == "standard"
    assert config.webrtc_enabled is False


def test_avatar_config_custom():
    config = AvatarConfig(
        enabled=True,
        character="custom-avatar",
        sdp_offer="v=0\r\no=- 123",
    )
    assert config.enabled is True
    assert config.sdp_offer is not None
