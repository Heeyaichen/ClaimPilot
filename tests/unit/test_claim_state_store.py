"""Unit tests for ClaimStateStore — mocked Cosmos DB."""

from datetime import datetime
from unittest.mock import MagicMock

from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    StepStatus,
)
from backend.services.claim_state_store import ClaimStateStore


def _base_record_dict(claim_id: str = "test") -> dict:
    """Return a minimal valid claim record dict for read_item mock."""
    now = datetime.utcnow().isoformat()
    return {
        "claim_id": claim_id,
        "status": "SUBMITTED",
        "submitted_at": now,
        "updated_at": now,
        "steps": [
            {
                "step": s.value,
                "status": "PENDING",
                "started_at": None,
                "completed_at": None,
                "output": {},
                "error": None,
            }
            for s in PipelineStep
        ],
        "image_blob_urls": [],
        "claimant_name": "",
        "policy_number": "",
    }


def _make_store() -> tuple[ClaimStateStore, MagicMock]:
    """Create a ClaimStateStore with a mocked Cosmos container."""
    mock_container = MagicMock()
    mock_container.upsert_item.return_value = None
    mock_container.read_item.return_value = _base_record_dict()

    store = ClaimStateStore.__new__(ClaimStateStore)
    store._container = mock_container
    store._endpoint = "https://mock.cosmos.azure.com"
    store._credential = MagicMock()
    store._database_name = "test-db"
    store._container_name = "test-claims"
    return store, mock_container


def test_create_claim_initializes_steps():
    store, mock_container = _make_store()
    record = ClaimRecord(claim_id="c1")

    result = store.create_claim(record)

    assert len(result.steps) == 8
    assert all(s.status == StepStatus.PENDING for s in result.steps)
    mock_container.upsert_item.assert_called_once()


def test_get_claim_found():
    store, mock_container = _make_store()
    mock_container.read_item.return_value = _base_record_dict("c1")

    result = store.get_claim("c1")
    assert result is not None
    assert result.claim_id == "c1"


def test_get_claim_not_found():
    store, mock_container = _make_store()
    mock_container.read_item.side_effect = Exception("not found")

    result = store.get_claim("missing")
    assert result is None


def test_update_step_running():
    store, mock_container = _make_store()

    result = store.update_step("c2", PipelineStep.INGEST_DOCUMENT, StepStatus.RUNNING)
    assert result is not None
    doc = result.model_dump(mode="json")
    step_states = [s for s in doc["steps"] if s["step"] == "INGEST_DOCUMENT"]
    assert step_states[0]["status"] == "RUNNING"
    assert step_states[0]["started_at"] is not None
    mock_container.upsert_item.assert_called_once()


def test_update_step_completed_with_output():
    store, mock_container = _make_store()

    output = {"claim_type": "AUTO", "confidence": 0.95}
    result = store.update_step("c3", PipelineStep.CLASSIFY, StepStatus.COMPLETED, output=output)
    assert result is not None
    step = [s for s in result.steps if s.step == PipelineStep.CLASSIFY][0]
    assert step.status == StepStatus.COMPLETED
    assert step.output == output
    assert step.completed_at is not None


def test_update_step_failed():
    store, mock_container = _make_store()

    result = store.update_step("c4", PipelineStep.INGEST_VOICE, StepStatus.FAILED, error="timeout")
    assert result is not None
    assert result.status == ClaimStatus.FAILED


def test_mark_claim_status():
    store, mock_container = _make_store()

    result = store.mark_claim_status("c5", ClaimStatus.APPROVED)
    assert result is not None
    assert result.status == ClaimStatus.APPROVED
