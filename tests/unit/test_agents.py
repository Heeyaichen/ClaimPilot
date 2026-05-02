"""Unit tests for agent stub outputs and pipeline wiring."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.classifier_agent import ClassifierAgent
from backend.agents.decision_agent import DecisionAgent
from backend.agents.extractor_agent import ExtractorAgent
from backend.agents.fraud_agent import FraudDetectionAgent
from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)


def _make_orchestrator():
    """Create an orchestrator with mock store and broadcaster."""
    from backend.pipeline.orchestrator import ClaimOrchestrator

    store = MagicMock()

    def fake_update(claim_id, step, status, output=None, error=None):
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = datetime.utcnow()
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    s.completed_at = datetime.utcnow()
                if output is not None:
                    s.output = output
        return record

    store.update_step.side_effect = fake_update

    def fake_get(claim_id):
        return ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )

    store.get_claim.side_effect = fake_get
    store.mark_claim_status.return_value = None

    broadcaster = MagicMock()
    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = True
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=broadcaster)
    return orch, broadcaster


# --- Agent stub outputs ---


def test_classifier_stub():
    result = ClassifierAgent._stub_classify(None)
    assert result.claim_type == "AUTO_PHYSICAL_DAMAGE"
    assert result.confidence > 0
    assert not result.requires_human_review


def test_extractor_stub():
    result = ExtractorAgent._stub_extract()
    assert result.policy_number is not None
    assert result.fields_extracted == 12
    assert result.confidence > 0


def test_fraud_stub():
    result = FraudDetectionAgent._stub_assess()
    assert result.score < 0.4
    assert result.recommendation == "proceed"


def test_decision_stub():
    result = DecisionAgent._stub_decide()
    assert result.decision == "APPROVE"
    assert result.approved_amount is not None
    assert len(result.reasoning_chain) > 0
    # All reasoning steps must have evidence sources
    for step in result.reasoning_chain:
        assert step.evidence_source != "stub"
        assert step.evidence_value is not None


# --- Pipeline wiring with stubs ---


@pytest.mark.asyncio
async def test_pipeline_runs_all_8_steps():
    orch, broadcaster = _make_orchestrator()
    record = ClaimRecord(
        claim_id="test-p3-001",
        claimant_name="John Doe",
        policy_number="AB12345678",
    )

    result = await orch.run_pipeline(record)
    # Stub policy AB12345678 is not in demo index → ESCALATED
    assert result.status in (ClaimStatus.APPROVED, ClaimStatus.ESCALATED)
    assert result.classification_result is not None
    assert result.extraction_result is not None
    assert result.fraud_result is not None
    assert result.decision_result is not None
    assert result.pipeline_duration_seconds is not None


@pytest.mark.asyncio
async def test_pipeline_classify_uses_agent():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-002", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    assert result.classification_result["claim_type"] == "AUTO_PHYSICAL_DAMAGE"


@pytest.mark.asyncio
async def test_pipeline_decision_has_reasoning_chain():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-003", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    chain = result.decision_result["reasoning_chain"]
    assert len(chain) >= 1
    for step in chain:
        assert "evidence_source" in step
        assert "evidence_value" in step


@pytest.mark.asyncio
async def test_pipeline_fraud_result_has_recommendation():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-004", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    assert result.fraud_result["recommendation"] in (
        "proceed",
        "adjuster_review",
        "escalate_siu",
    )


@pytest.mark.asyncio
async def test_pipeline_emits_signalr_events():
    orch, broadcaster = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-005", claimant_name="John Doe", policy_number="AB12345678")
    await orch.run_pipeline(record)
    assert broadcaster.broadcast_step_event.call_count > 0


@pytest.mark.asyncio
async def test_pipeline_voice_skip():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(
        claim_id="test-p3-006",
        audio_blob_url=None,
        claimant_name="John Doe",
        policy_number="AB12345678",
    )
    result = await orch.run_pipeline(record)
    assert result.voice_transcript["status"] == "skipped"


@pytest.mark.asyncio
async def test_pipeline_failure_sets_failed():
    store = MagicMock()
    call_count = 0

    def failing_update(claim_id, step, status, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 3:
            raise RuntimeError("Simulated failure")
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = datetime.utcnow()
                if status in (StepStatus.COMPLETED, StepStatus.FAILED):
                    s.completed_at = datetime.utcnow()
        return record

    store.update_step.side_effect = failing_update
    store.get_claim.side_effect = lambda cid: ClaimRecord(
        claim_id=cid, steps=[PipelineStepState(step=s) for s in PipelineStep]
    )

    from backend.pipeline.orchestrator import ClaimOrchestrator

    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = True
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=MagicMock())
    record = ClaimRecord(claim_id="test-p3-007", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    assert result.status == ClaimStatus.FAILED
