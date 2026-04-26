"""Unit tests for Voice Live session service."""

from unittest.mock import MagicMock, patch

import pytest

from backend.models.voice_live import (
    SessionStatus,
    VoiceLiveEventType,
    VoiceLiveSessionConfig,
)
from backend.services.claim_lookup_tool import ClaimLookupTool
from backend.services.voice_live import VoiceLiveService
from tests.unit.test_claim_lookup_tool import _mock_store, _mock_store_not_found


def _service_with_store(store=None) -> VoiceLiveService:
    lookup = ClaimLookupTool(state_store=store or _mock_store())
    return VoiceLiveService(claim_lookup=lookup)


def test_create_adjuster_session_success():
    service = _service_with_store()
    session = service.create_adjuster_session("c1", "adjuster-1")
    assert session.claim_id == "c1"
    assert session.status == SessionStatus.CONNECTING
    assert session.session_id
    assert session.token.startswith("cp-")


def test_create_adjuster_session_claim_not_found():
    service = _service_with_store(_mock_store_not_found())
    with pytest.raises(ValueError, match="not found"):
        service.create_adjuster_session("nonexistent")


def test_build_session_config():
    service = _service_with_store()
    config = service.build_session_config("c1")
    assert isinstance(config, VoiceLiveSessionConfig)
    assert "adjuster copilot" in config.instructions.lower()
    assert len(config.tools) > 0
    assert config.turn_detection["type"] == "azure_semantic_vad"


def test_build_session_config_includes_claim_context():
    service = _service_with_store()
    config = service.build_session_config("c1")
    assert "c1" in config.instructions
    assert "APPROVE" in config.instructions


@patch("backend.services.voice_live.get_settings")
def test_build_session_config_mcp_enabled(mock_settings):
    mock_settings.return_value = MagicMock(
        voice_live_voice="en-US-AvaMultilingualNeural",
        voice_live_enable_mcp=True,
        voice_live_mcp_server_url="https://mcp.example.com/claim",
    )
    service = _service_with_store()
    config = service.build_session_config("c1")
    assert len(config.mcp_servers) == 1
    assert config.mcp_servers[0]["url"] == "https://mcp.example.com/claim"


def test_handle_tool_call():
    service = _service_with_store()
    result = service.handle_tool_call("get_fraud_score", {"claim_id": "c1"})
    import json

    parsed = json.loads(result)
    assert parsed["found"] is True
    assert parsed["fraud_score"] == 0.18


def test_process_voice_event_tool_call():
    service = _service_with_store()
    event = {
        "type": "response.function_call_arguments.done",
        "name": "get_claim_summary",
        "call_id": "call-123",
        "arguments": '{"claim_id": "c1"}',
    }
    response = service.process_voice_event(event)
    assert response is not None
    assert response.event_type == VoiceLiveEventType.TOOL_RESULT
    assert response.data["item"]["call_id"] == "call-123"


def test_process_voice_event_transcript():
    service = _service_with_store()
    event = {
        "type": "response.transcript",
        "role": "assistant",
        "text": "The fraud score is 0.18",
    }
    response = service.process_voice_event(event)
    assert response is not None
    assert response.event_type == VoiceLiveEventType.TRANSCRIPT


def test_process_voice_event_passthrough():
    service = _service_with_store()
    event = {"type": "session.created"}
    response = service.process_voice_event(event)
    assert response is None


def test_process_voice_event_invalid_json_arguments():
    service = _service_with_store()
    event = {
        "type": "response.function_call_arguments.done",
        "name": "get_claim_summary",
        "call_id": "call-456",
        "arguments": "not-valid-json",
    }
    response = service.process_voice_event(event)
    assert response is not None
    # Should still process with empty arguments
    assert response.event_type == VoiceLiveEventType.TOOL_RESULT


def test_get_avatar_config():
    service = _service_with_store()
    config = service.get_avatar_config()
    assert config.enabled is False


def test_session_token_format():
    service = _service_with_store()
    session = service.create_adjuster_session("c1", "a1")
    assert session.token.startswith("cp-")
    assert len(session.token) > 10
    # Each session gets a unique token
    session2 = service.create_adjuster_session("c1", "a1")
    assert session.token != session2.token  # different session_id → different token
