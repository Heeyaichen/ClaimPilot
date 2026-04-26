"""Unit tests for adjuster API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _mock_voice_service():
    from backend.models.voice_live import AdjusterSessionResponse, SessionStatus

    session = AdjusterSessionResponse(
        session_id="test-session",
        claim_id="c1",
        ws_url="wss://example.com/voice",
        token="cp-test-token",
        status=SessionStatus.CONNECTING,
    )
    mock = MagicMock()
    mock.create_adjuster_session.return_value = session
    mock.build_session_config.return_value = MagicMock(
        model_dump=lambda: {"modalities": ["text", "audio"], "voice": "test"},
    )
    mock.process_voice_event.return_value = None
    return mock


def _mock_lookup_tool():
    from backend.models.voice_live import ClaimLookupResult

    mock = MagicMock()
    mock.get_claim_summary.return_value = ClaimLookupResult(
        claim_id="c1",
        found=True,
        summary="Test claim summary",
        decision="APPROVE",
    )
    return mock


@patch("backend.api.adjuster_routes._get_voice_service")
def test_get_session_url_success(mock_get_service, client):
    mock_get_service.return_value = _mock_voice_service()
    response = client.get("/api/v1/adjuster/session-url?claim_id=c1")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session"
    assert data["claim_id"] == "c1"
    assert data["ws_url"] == "wss://example.com/voice"


@patch("backend.api.adjuster_routes._get_voice_service")
def test_get_session_url_claim_not_found(mock_get_service, client):
    mock_service = _mock_voice_service()
    mock_service.create_adjuster_session.side_effect = ValueError("Claim c1 not found")
    mock_get_service.return_value = mock_service
    response = client.get("/api/v1/adjuster/session-url?claim_id=c1")
    assert response.status_code == 404


@patch("backend.api.adjuster_routes._get_lookup_tool")
def test_get_claim_context_success(mock_get_tool, client):
    mock_get_tool.return_value = _mock_lookup_tool()
    response = client.get("/api/v1/adjuster/claim/c1")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["summary"] == "Test claim summary"


@patch("backend.api.adjuster_routes._get_lookup_tool")
def test_get_claim_context_not_found(mock_get_tool, client):
    from backend.models.voice_live import ClaimLookupResult

    mock_tool = MagicMock()
    mock_tool.get_claim_summary.return_value = ClaimLookupResult(
        claim_id="c1", found=False, error="Claim not found"
    )
    mock_get_tool.return_value = mock_tool
    response = client.get("/api/v1/adjuster/claim/c1")
    assert response.status_code == 404
