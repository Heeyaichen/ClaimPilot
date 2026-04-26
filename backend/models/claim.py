"""Claim pipeline models — state machine, step tracking, API request/response."""

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
    """The 7 visible pipeline steps, in execution order."""

    CLAIM_RECEIVED = "CLAIM_RECEIVED"
    INGEST_DOCUMENT = "INGEST_DOCUMENT"
    INGEST_IMAGES = "INGEST_IMAGES"
    INGEST_VOICE = "INGEST_VOICE"
    CLASSIFY_STUB = "CLASSIFY_STUB"
    EXTRACT_VALIDATE_STUB = "EXTRACT_VALIDATE_STUB"
    DECIDE_STUB = "DECIDE_STUB"


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
    PipelineStep.CLASSIFY_STUB: ClaimStatus.CLASSIFYING,
    PipelineStep.EXTRACT_VALIDATE_STUB: ClaimStatus.EXTRACTING,
    PipelineStep.DECIDE_STUB: ClaimStatus.DECIDING,
}


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

    claim_id: str
    status: ClaimStatus = ClaimStatus.SUBMITTED
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    decision_result: dict[str, Any] | None = None

    # Metadata
    claimant_name: str = ""
    policy_number: str = ""
    pipeline_duration_seconds: float | None = None


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
    total_steps: int = 7
    steps: list[PipelineStepState] = Field(default_factory=list)
    submitted_at: datetime
    updated_at: datetime
    partial_results: dict[str, Any] = Field(default_factory=dict)
