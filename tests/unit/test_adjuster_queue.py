"""Unit tests for adjuster queue endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_adjuster_queue_returns_empty(client):
    """Queue endpoint should return empty list when Cosmos is empty."""
    with patch("backend.api.adjuster_routes._get_state_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store._get_container.return_value.query_items.return_value = []
        mock_store_fn.return_value = mock_store

        response = client.get("/api/v1/adjuster/queue")
        assert response.status_code == 200
        data = response.json()
        assert data["claims"] == []
        assert data["total"] == 0


def test_adjuster_queue_priority_sorting(client):
    """High fraud risk claims should sort before low risk."""
    with patch("backend.api.adjuster_routes._get_state_store") as mock_store_fn:
        mock_store = MagicMock()
        # Two claims: low fraud then high fraud
        mock_store._get_container.return_value.query_items.return_value = [
            {
                "claim_id": "low-risk",
                "status": "ESCALATED",
                "fraud_result": {"score": 0.2, "flags": [], "recommendation": "proceed"},
                "updated_at": "2026-01-01T12:00:00",
            },
            {
                "claim_id": "high-risk",
                "status": "ESCALATED",
                "fraud_result": {"score": 0.85, "flags": ["suspicious"], "recommendation": "escalate_siu"},
                "updated_at": "2026-01-01T12:00:00",
            },
        ]
        mock_store_fn.return_value = mock_store

        response = client.get("/api/v1/adjuster/queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data["claims"]) == 2
        # High fraud (score >= 0.7) should come first
        assert data["claims"][0]["claim_id"] == "high-risk"


def test_adjuster_queue_pagination(client):
    """Queue should support page and page_size parameters."""
    with patch("backend.api.adjuster_routes._get_state_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store._get_container.return_value.query_items.return_value = []
        mock_store_fn.return_value = mock_store

        response = client.get("/api/v1/adjuster/queue?page=2&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
