"""Unit tests for claim pipeline models."""

from datetime import datetime

from backend.models.claim import (
    STEP_TO_CLAIM_STATUS,
    ClaimRecord,
    ClaimStatus,
    ClaimStatusResponse,
    ClaimSubmissionRequest,
    ClaimSubmissionResponse,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)


def test_claim_status_values():
    assert ClaimStatus.SUBMITTED.value == "SUBMITTED"
    assert ClaimStatus.APPROVED.value == "APPROVED"
    assert ClaimStatus.FAILED.value == "FAILED"


def test_pipeline_step_order():
    steps = list(PipelineStep)
    assert len(steps) == 7
    assert steps[0] == PipelineStep.CLAIM_RECEIVED
    assert steps[-1] == PipelineStep.DECIDE_STUB


def test_step_status_values():
    assert StepStatus.PENDING.value == "PENDING"
    assert StepStatus.COMPLETED.value == "COMPLETED"


def test_step_to_claim_status_mapping():
    assert STEP_TO_CLAIM_STATUS[PipelineStep.CLAIM_RECEIVED] == ClaimStatus.SUBMITTED
    assert STEP_TO_CLAIM_STATUS[PipelineStep.INGEST_DOCUMENT] == ClaimStatus.INGESTING
    assert STEP_TO_CLAIM_STATUS[PipelineStep.CLASSIFY_STUB] == ClaimStatus.CLASSIFYING
    assert STEP_TO_CLAIM_STATUS[PipelineStep.DECIDE_STUB] == ClaimStatus.DECIDING
    assert len(STEP_TO_CLAIM_STATUS) == len(PipelineStep)


def test_pipeline_step_state_defaults():
    state = PipelineStepState(step=PipelineStep.CLAIM_RECEIVED)
    assert state.status == StepStatus.PENDING
    assert state.started_at is None
    assert state.completed_at is None
    assert state.output == {}
    assert state.error is None


def test_claim_record_defaults():
    record = ClaimRecord(claim_id="abc123")
    assert record.status == ClaimStatus.SUBMITTED
    assert record.steps == []
    assert record.image_blob_urls == []
    assert record.claimant_name == ""
    assert record.pipeline_duration_seconds is None


def test_claim_record_serialization():
    record = ClaimRecord(
        claim_id="test-001",
        claimant_name="Jane Doe",
        policy_number="POL-001",
        steps=[PipelineStepState(step=PipelineStep.CLAIM_RECEIVED, status=StepStatus.COMPLETED)],
    )
    data = record.model_dump(mode="json")
    assert data["claim_id"] == "test-001"
    assert data["status"] == "SUBMITTED"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["step"] == "CLAIM_RECEIVED"


def test_claim_submission_request():
    req = ClaimSubmissionRequest(claimant_name="John", policy_number="POL-002")
    assert req.claimant_name == "John"
    assert req.policy_number == "POL-002"


def test_claim_submission_response():
    resp = ClaimSubmissionResponse(
        claim_id="abc",
        status=ClaimStatus.SUBMITTED,
        status_url="/api/v1/claims/abc/status",
    )
    assert resp.claim_id == "abc"
    assert resp.status_url == "/api/v1/claims/abc/status"


def test_claim_status_response():
    resp = ClaimStatusResponse(
        claim_id="xyz",
        status=ClaimStatus.INGESTING,
        current_step="INGEST_DOCUMENT",
        submitted_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    assert resp.total_steps == 7
    assert resp.steps == []
    assert resp.partial_results == {}
