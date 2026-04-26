"""Claim pipeline models — state machine, step tracking, agent outputs, API request/response."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ClaimStatus(StrEnum):
    """Top-level claim lifecycle status."""

    SUBMITTED = "SUBMITTED"
    INGESTING = "INGESTING"
    CLASSIFYING = "CLASSIFYING"
    EXTRACTING = "EXTRACTING"
    FRAUD_SCREENING = "FRAUD_SCREENING"
    DECIDING = "DECIDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class PipelineStep(StrEnum):
    """Pipeline steps in execution order — 8 steps total."""

    CLAIM_RECEIVED = "CLAIM_RECEIVED"
    INGEST_DOCUMENT = "INGEST_DOCUMENT"
    INGEST_IMAGES = "INGEST_IMAGES"
    INGEST_VOICE = "INGEST_VOICE"
    CLASSIFY = "CLASSIFY"
    EXTRACT_VALIDATE = "EXTRACT_VALIDATE"
    FRAUD_SCREENING = "FRAUD_SCREENING"
    DECIDE = "DECIDE"


class StepStatus(StrEnum):
    """Status of a single pipeline step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# Mapping from step to claim status for state transitions
STEP_TO_CLAIM_STATUS: dict[PipelineStep, ClaimStatus] = {
    PipelineStep.CLAIM_RECEIVED: ClaimStatus.SUBMITTED,
    PipelineStep.INGEST_DOCUMENT: ClaimStatus.INGESTING,
    PipelineStep.INGEST_IMAGES: ClaimStatus.INGESTING,
    PipelineStep.INGEST_VOICE: ClaimStatus.INGESTING,
    PipelineStep.CLASSIFY: ClaimStatus.CLASSIFYING,
    PipelineStep.EXTRACT_VALIDATE: ClaimStatus.EXTRACTING,
    PipelineStep.FRAUD_SCREENING: ClaimStatus.FRAUD_SCREENING,
    PipelineStep.DECIDE: ClaimStatus.DECIDING,
}

TOTAL_PIPELINE_STEPS = len(PipelineStep)


# --- Agent output models ---


class ClaimClassification(BaseModel):
    """Output of the ClassifierAgent."""

    claim_type: str = Field(description="AUTO_PHYSICAL_DAMAGE | TOTAL_LOSS | THEFT | LIABILITY")
    confidence: float = Field(ge=0.0, le=1.0)
    routing_rationale: str
    requires_human_review: bool = False
    review_reason: str | None = None


class ExtractedClaimFields(BaseModel):
    """Output of the ExtractorAgent."""

    policy_number: str | None = None
    applicant_name: str | None = None
    loss_date: str | None = None
    loss_description: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vin: str | None = None
    estimated_repair_amount: float | None = None
    deductible: float | None = None
    coverage_limit: float | None = None
    policy_expiry: str | None = None
    fields_extracted: int = 0
    validation_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class FraudRiskScore(BaseModel):
    """Output of the FraudDetectionAgent."""

    score: float = Field(ge=0.0, le=1.0)
    signals: dict[str, float] = Field(
        default_factory=dict, description="signal_name -> individual score"
    )
    flags: list[str] = Field(default_factory=list, description="anomaly descriptions")
    recommendation: str = Field(description="proceed | adjuster_review | escalate_siu")


class ReasoningStep(BaseModel):
    """Single step in the decision reasoning chain."""

    step: str
    conclusion: str
    evidence_source: str
    evidence_value: str | float | bool


class AdjudicationDecision(BaseModel):
    """Output of the DecisionAgent."""

    decision: str = Field(description="APPROVE | REJECT | ESCALATE")
    confidence: float = Field(ge=0.0, le=1.0)
    approved_amount: float | None = None
    rejection_reason: str | None = None
    escalation_reason: str | None = None
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)


# --- Pipeline state models ---


class PipelineStepState(BaseModel):
    """State of a single pipeline step within a claim."""

    step: PipelineStep
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ClaimRecord(BaseModel):
    """Full claim record persisted in Cosmos DB."""

    model_config = {"populate_by_name": True}

    claim_id: str
    status: ClaimStatus = ClaimStatus.SUBMITTED
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Cosmos DB compatibility fields
    id: str = ""  # aliases claim_id for Cosmos DB
    policyId: str = ""  # partition key — aliases policy_number

    # File references
    form_blob_url: str | None = None
    image_blob_urls: list[str] = Field(default_factory=list)
    audio_blob_url: str | None = None

    # Pipeline progress
    steps: list[PipelineStepState] = Field(default_factory=list)

    # Accumulated pipeline outputs (populated progressively)
    doc_extraction: dict[str, Any] | None = None
    image_analysis: dict[str, Any] | None = None
    voice_transcript: dict[str, Any] | None = None
    classification_result: dict[str, Any] | None = None
    extraction_result: dict[str, Any] | None = None
    fraud_result: dict[str, Any] | None = None
    decision_result: dict[str, Any] | None = None

    # Metadata
    claimant_name: str = ""
    policy_number: str = ""
    pipeline_duration_seconds: float | None = None

    def model_post_init(self, __context: object) -> None:
        """Sync Cosmos DB compatibility fields after initialization."""
        if not self.id:
            self.id = self.claim_id
        if not self.policyId:
            self.policyId = self.policy_number or self.claim_id


class ClaimSubmissionRequest(BaseModel):
    """Request body for POST /api/v1/claims."""

    claimant_name: str = ""
    policy_number: str = ""


class ClaimSubmissionResponse(BaseModel):
    """Response for POST /api/v1/claims — 202 Accepted."""

    claim_id: str
    status: ClaimStatus
    status_url: str


class ClaimStatusResponse(BaseModel):
    """Response for GET /api/v1/claims/{claim_id}/status."""

    claim_id: str
    status: ClaimStatus
    current_step: str
    total_steps: int = TOTAL_PIPELINE_STEPS
    steps: list[PipelineStepState] = Field(default_factory=list)
    submitted_at: datetime
    updated_at: datetime
    partial_results: dict[str, Any] = Field(default_factory=dict)
