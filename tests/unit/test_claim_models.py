"""Unit tests for claim pipeline models."""

from datetime import datetime

from backend.models.claim import (
    STEP_TO_CLAIM_STATUS,
    TOTAL_PIPELINE_STEPS,
    AdjudicationDecision,
    ClaimClassification,
    ClaimRecord,
    ClaimStatus,
    ClaimStatusResponse,
    ClaimSubmissionRequest,
    ClaimSubmissionResponse,
    ExtractedClaimFields,
    FraudRiskScore,
    PipelineStep,
    PipelineStepState,
    ReasoningStep,
    StepStatus,
)


def test_claim_status_values():
    assert ClaimStatus.SUBMITTED.value == "SUBMITTED"
    assert ClaimStatus.APPROVED.value == "APPROVED"
    assert ClaimStatus.FAILED.value == "FAILED"


def test_pipeline_step_order():
    steps = list(PipelineStep)
    assert len(steps) == 8
    assert steps[0] == PipelineStep.CLAIM_RECEIVED
    assert steps[-1] == PipelineStep.DECIDE


def test_step_status_values():
    assert StepStatus.PENDING.value == "PENDING"
    assert StepStatus.COMPLETED.value == "COMPLETED"


def test_step_to_claim_status_mapping():
    assert STEP_TO_CLAIM_STATUS[PipelineStep.CLAIM_RECEIVED] == ClaimStatus.SUBMITTED
    assert STEP_TO_CLAIM_STATUS[PipelineStep.INGEST_DOCUMENT] == ClaimStatus.INGESTING
    assert STEP_TO_CLAIM_STATUS[PipelineStep.CLASSIFY] == ClaimStatus.CLASSIFYING
    assert STEP_TO_CLAIM_STATUS[PipelineStep.FRAUD_SCREENING] == ClaimStatus.FRAUD_SCREENING
    assert STEP_TO_CLAIM_STATUS[PipelineStep.DECIDE] == ClaimStatus.DECIDING
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
    assert resp.total_steps == TOTAL_PIPELINE_STEPS
    assert resp.steps == []
    assert resp.partial_results == {}


# --- Agent output model tests ---


def test_claim_classification_model():
    c = ClaimClassification(
        claim_type="AUTO_PHYSICAL_DAMAGE",
        confidence=0.93,
        routing_rationale="Test",
    )
    assert c.claim_type == "AUTO_PHYSICAL_DAMAGE"
    assert not c.requires_human_review


def test_extracted_claim_fields_model():
    e = ExtractedClaimFields(
        policy_number="AB12345678",
        vehicle_make="Toyota",
        fields_extracted=2,
        confidence=0.9,
    )
    assert e.policy_number == "AB12345678"
    assert e.validation_flags == []


def test_fraud_risk_score_model():
    f = FraudRiskScore(score=0.5, signals={"damage_consistency": 0.5}, recommendation="adjuster_review")
    assert f.score == 0.5
    assert f.recommendation == "adjuster_review"


def test_adjudication_decision_model():
    d = AdjudicationDecision(
        decision="APPROVE",
        confidence=0.9,
        approved_amount=5000.0,
        reasoning_chain=[
            ReasoningStep(
                step="Coverage check",
                conclusion="Active",
                evidence_source="doc.field",
                evidence_value="2026-11-30",
            )
        ],
    )
    assert d.decision == "APPROVE"
    assert len(d.reasoning_chain) == 1
