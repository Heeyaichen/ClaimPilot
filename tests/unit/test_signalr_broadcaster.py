"""Unit tests for SignalRBroadcaster — mocked HTTP calls."""

from unittest.mock import MagicMock, patch

from backend.services.signalr import SignalRBroadcaster


def _make_broadcaster() -> tuple[SignalRBroadcaster, MagicMock]:
    """Create a broadcaster with mocked credential and httpx."""
    mock_credential = MagicMock()
    mock_token = MagicMock()
    mock_token.token = "fake-token"
    mock_credential.get_token.return_value = mock_token
    broadcaster = SignalRBroadcaster(
        endpoint="https://mock.signalr.service.signalr.net",
        hub_name="claims",
        credential=mock_credential,
    )
    return broadcaster, mock_credential


@patch("backend.services.signalr.httpx.Client")
def test_broadcast_step_event_success(mock_client_cls):
    broadcaster, mock_credential = _make_broadcaster()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client_instance

    broadcaster.broadcast_step_event(
        claim_id="c1", step="INGEST_DOCUMENT", status="stepStarted"
    )

    mock_client_instance.post.assert_called_once()
    call_kwargs = mock_client_instance.post.call_args
    body = call_kwargs.kwargs["json"]
    assert body["target"] == "pipelineEvent"
    mock_credential.get_token.assert_called_once()


@patch("backend.services.signalr.httpx.Client")
def test_broadcast_failure_does_not_raise(mock_client_cls):
    broadcaster, _ = _make_broadcaster()
    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.side_effect = Exception("network error")
    mock_client_cls.return_value = mock_client_instance

    # Should not raise — failures are swallowed
    broadcaster.broadcast_step_event(
        claim_id="c1", step="DECIDE_STUB", status="stepCompleted"
    )


def test_build_url():
    broadcaster, _ = _make_broadcaster()
    url = broadcaster._build_url()
    assert url == "https://mock.signalr.service.signalr.net/api/v1/hubs/claims"
