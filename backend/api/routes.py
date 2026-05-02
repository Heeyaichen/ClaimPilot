"""Claim API routes — POST /api/v1/claims and GET /api/v1/claims/{claim_id}/status."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    ClaimStatusResponse,
    ClaimSubmissionResponse,
)
from backend.pipeline.orchestrator import ClaimOrchestrator
from backend.services.blob_storage import BlobStorageService
from backend.services.claim_state_store import ClaimStateStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


def _get_blob_service() -> BlobStorageService:
    return BlobStorageService()


def _get_state_store() -> ClaimStateStore:
    return ClaimStateStore()


def _get_orchestrator(store: ClaimStateStore) -> ClaimOrchestrator:
    return ClaimOrchestrator(state_store=store)


def _current_step(record: ClaimRecord) -> str:
    """Determine the current step label from the record."""
    for step_state in record.steps:
        if step_state.status.value in ("RUNNING", "PENDING"):
            return step_state.step.value
    return record.steps[-1].step.value if record.steps else "UNKNOWN"


@router.post("", status_code=202, response_model=ClaimSubmissionResponse)
async def submit_claim(
    claimant_name: str = Form(""),
    policy_number: str = Form(""),
    form: UploadFile | None = File(None),
    images: list[UploadFile] = File(default_factory=list),
    audio: UploadFile | None = File(None),
) -> Any:
    """Submit a new insurance claim with optional file attachments.

    Accepts multipart/form-data with:
    - form: claim form document (PDF, etc.)
    - images: damage photos
    - audio: voice recording
    - claimant_name, policy_number: metadata
    """
    claim_id = uuid.uuid4().hex[:12]
    logger.info("Received claim submission %s", claim_id)

    blob_service = _get_blob_service()
    store = _get_state_store()

    # Upload files to blob storage
    form_blob_url: str | None = None
    image_blob_urls: list[str] = []
    audio_blob_url: str | None = None

    if form and form.filename:
        data = await form.read()
        form_blob_url = blob_service.upload_file(data, form.filename, claim_id, "forms")

    for img in images:
        if img.filename:
            data = await img.read()
            url = blob_service.upload_file(data, img.filename, claim_id, "images")
            image_blob_urls.append(url)

    if audio and audio.filename:
        data = await audio.read()
        audio_blob_url = blob_service.upload_file(data, audio.filename, claim_id, "audio")

    # Create claim record
    record = ClaimRecord(
        claim_id=claim_id,
        status=ClaimStatus.SUBMITTED,
        submitted_at=datetime.utcnow(),
        form_blob_url=form_blob_url,
        image_blob_urls=image_blob_urls,
        audio_blob_url=audio_blob_url,
        claimant_name=claimant_name,
        policy_number=policy_number,
    )
    store.create_claim(record)

    # Start pipeline (direct invocation for local dev; Service Bus trigger in prod)
    orchestrator = _get_orchestrator(store)
    try:
        await orchestrator.run_pipeline(record)
    except Exception:
        logger.exception("Pipeline execution failed for claim %s", claim_id)

    return ClaimSubmissionResponse(
        claim_id=claim_id,
        status=ClaimStatus.SUBMITTED,
        status_url=f"/api/v1/claims/{claim_id}/status",
    )


@router.get("/{claim_id}/status", response_model=ClaimStatusResponse)
async def get_claim_status(claim_id: str) -> Any:
    """Get the current processing status of a claim."""
    store = _get_state_store()
    record = store.get_claim(claim_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # Collect partial results from completed steps
    partial_results: dict[str, Any] = {}
    for field in (
        "doc_extraction",
        "image_analysis",
        "voice_transcript",
        "classification_result",
        "extraction_result",
        "decision_result",
        "evidence_consistency",
    ):
        value = getattr(record, field, None)
        if value is not None:
            partial_results[field] = value

    return ClaimStatusResponse(
        claim_id=record.claim_id,
        status=record.status,
        current_step=_current_step(record),
        steps=record.steps,
        submitted_at=record.submitted_at,
        updated_at=record.updated_at,
        partial_results=partial_results,
    )
