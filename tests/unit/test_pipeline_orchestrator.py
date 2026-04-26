"""Unit tests for ClaimOrchestrator — fully mocked state store and broadcaster."""

from datetime import datetime
from unittest.mock import MagicMock

from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)
from backend.pipeline.orchestrator import ClaimOrchestrator


def _make_store() -> tuple[MagicMock, list[dict]]:
    """Create a mock state store that tracks upserted items."""
    items: list[dict] = []

    store = MagicMock()

    # update_step returns the updated record
    def fake_update(claim_id, step, status, output=None, error=None):
        now = datetime.utcnow()
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = now
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    s.completed_at = now
                if output is not None:
                    s.output = output
                if error is not None:
                    s.error = error
        return record

    store.update_step.side_effect = fake_update

    # get_claim returns a basic record
    def fake_get(claim_id):
        return ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )

    store.get_claim.side_effect = fake_get
    store.mark_claim_status.return_value = None
    return store, items


def _make_orchestrator() -> tuple[ClaimOrchestrator, MagicMock, list[dict]]:
    store, items = _make_store()
    broadcaster = MagicMock()
    orch = ClaimOrchestrator(state_store=store, broadcaster=broadcaster)
    return orch, broadcaster, items


def test_run_pipeline_completes_all_steps():
    orch, broadcaster, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-001")

    result = orch.run_pipeline(record)

    assert result.status == ClaimStatus.APPROVED
    assert result.classification_result is not None
    assert result.extraction_result is not None
    assert result.fraud_result is not None
    assert result.decision_result is not None
    assert result.pipeline_duration_seconds is not None


def test_run_pipeline_emits_signalr_events():
    orch, broadcaster, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-002")

    orch.run_pipeline(record)

    assert broadcaster.broadcast_step_event.call_count > 0


def test_run_pipeline_with_no_audio_skips_voice():
    orch, _, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-003", audio_blob_url=None)

    result = orch.run_pipeline(record)

    assert result.voice_transcript == {"status": "skipped", "note": "No audio provided"}


def test_run_pipeline_with_audio_processes_voice():
    orch, _, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-004", audio_blob_url="https://blob/audio.wav")

    result = orch.run_pipeline(record)

    assert result.voice_transcript is not None
    assert result.voice_transcript["status"] == "stub"


def test_run_pipeline_failure_sets_failed_status():
    store, _ = _make_store()
    call_count = 0
    original_update = store.update_step.side_effect

    def failing_update(claim_id, step, status, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            raise RuntimeError("Simulated failure")
        return original_update(claim_id, step, status, **kwargs)

    store.update_step.side_effect = failing_update
    orch = ClaimOrchestrator(state_store=store, broadcaster=MagicMock())
    record = ClaimRecord(claim_id="test-005")

    result = orch.run_pipeline(record)

    assert result.status == ClaimStatus.FAILED
    store.mark_claim_status.assert_called_with("test-005", ClaimStatus.FAILED)
