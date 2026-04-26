"""Claim processing orchestrator — Durable Functions pattern.

Implements the 7-step claim pipeline:
1. CLAIM_RECEIVED — validate input, mark received
2-4. INGEST_DOCUMENT, INGEST_IMAGES, INGEST_VOICE — fan-out in parallel
5. CLASSIFY_STUB — stub classification activity
6. EXTRACT_VALIDATE_STUB — stub extraction/validation
7. DECIDE_STUB — stub decision

Can run as a pure-Python orchestrator for local dev (no Azure Functions
runtime required) or as Durable Functions activities in Azure.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    StepStatus,
)
from backend.services.claim_state_store import ClaimStateStore
from backend.services.signalr import SignalRBroadcaster

logger = logging.getLogger(__name__)

# --- Stub results for Phase 2 (replaced by real agents in Phase 3) ---

STUB_CLASSIFICATION = {
    "claim_type": "AUTO_PHYSICAL_DAMAGE",
    "confidence": 0.93,
    "routing_rationale": "Stub: auto physical damage detected",
    "requires_human_review": False,
}

STUB_EXTRACTION = {
    "fields_extracted": 12,
    "validation_flags": [],
    "confidence": 0.91,
    "note": "Stub: extraction not yet implemented",
}

STUB_DECISION = {
    "decision": "APPROVE",
    "confidence": 0.88,
    "approved_amount": 8400.00,
    "reasoning_chain": [
        {
            "step": "Coverage verified",
            "conclusion": "Stub: policy active on loss date",
            "evidence_source": "stub",
            "evidence_value": "stub",
        }
    ],
    "note": "Stub: decision agent not yet implemented",
}


class ClaimOrchestrator:
    """Orchestrates the 7-step claim processing pipeline.

    Designed to work both locally (for dev/testing) and as
    Durable Functions activities in production.
    """

    def __init__(
        self,
        state_store: ClaimStateStore,
        broadcaster: SignalRBroadcaster | None = None,
    ) -> None:
        self._store = state_store
        self._broadcaster = broadcaster

    def _emit(
        self,
        claim_id: str,
        step: PipelineStep,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast a SignalR event if broadcaster is configured."""
        if self._broadcaster:
            self._broadcaster.broadcast_step_event(
                claim_id=claim_id,
                step=step.value,
                status=status,
                payload=payload,
            )

    def _start_step(self, claim_id: str, step: PipelineStep) -> None:
        """Mark a step as RUNNING and emit stepStarted."""
        self._store.update_step(claim_id, step, StepStatus.RUNNING)
        self._emit(claim_id, step, "stepStarted")

    def _complete_step(
        self,
        claim_id: str,
        step: PipelineStep,
        output: dict[str, Any] | None = None,
    ) -> None:
        """Mark a step as COMPLETED and emit stepCompleted."""
        record = self._store.update_step(
            claim_id, step, StepStatus.COMPLETED, output=output
        )
        duration_ms = 0
        if record:
            for s in record.steps:
                if s.step == step and s.started_at and s.completed_at:
                    duration_ms = int(
                        (s.completed_at - s.started_at).total_seconds() * 1000
                    )
        self._emit(claim_id, step, "stepCompleted", {"durationMs": duration_ms})

    def _fail_step(self, claim_id: str, step: PipelineStep, error: str) -> None:
        """Mark a step as FAILED and emit stepFailed."""
        self._store.update_step(claim_id, step, StepStatus.FAILED, error=error)
        self._emit(claim_id, step, "stepFailed", {"error": error, "willRetry": False})

    def run_pipeline(self, record: ClaimRecord) -> ClaimRecord:
        """Execute the full 7-step pipeline for a claim.

        Args:
            record: The initial claim record (already created in Cosmos).

        Returns:
            Updated ClaimRecord with all pipeline outputs.
        """
        claim_id = record.claim_id
        logger.info("Starting pipeline for claim %s", claim_id)

        try:
            # Step 1: CLAIM_RECEIVED
            self._start_step(claim_id, PipelineStep.CLAIM_RECEIVED)
            self._complete_step(claim_id, PipelineStep.CLAIM_RECEIVED)

            # Steps 2-4: Fan-out ingestion (parallel conceptually,
            # executed sequentially here for simplicity; Durable Functions
            # fan_out/fan_in handles true parallelism in production)
            doc_output = self._step_ingest_document(claim_id, record.form_blob_url)
            image_output = self._step_ingest_images(claim_id, record.image_blob_urls)
            voice_output = self._step_ingest_voice(claim_id, record.audio_blob_url)

            # Step 5: CLASSIFY_STUB
            classify_output = self._step_classify(claim_id)

            # Step 6: EXTRACT_VALIDATE_STUB
            extract_output = self._step_extract_validate(claim_id)

            # Step 7: DECIDE_STUB
            decision_output = self._step_decide(claim_id)

            # Update final record
            record = self._store.get_claim(claim_id) or record
            record.doc_extraction = doc_output
            record.image_analysis = image_output
            record.voice_transcript = voice_output
            record.classification_result = classify_output
            record.extraction_result = extract_output
            record.decision_result = decision_output
            record.status = ClaimStatus.APPROVED
            record.updated_at = datetime.utcnow()
            record.pipeline_duration_seconds = (
                record.updated_at - record.submitted_at
            ).total_seconds()
            self._store.mark_claim_status(claim_id, ClaimStatus.APPROVED)

            self._emit(
                claim_id,
                PipelineStep.DECIDE_STUB,
                "claimDecided",
                {"outcome": "APPROVED"},
            )
            logger.info("Pipeline completed for claim %s", claim_id)

        except Exception:
            logger.exception("Pipeline failed for claim %s", claim_id)
            self._store.mark_claim_status(claim_id, ClaimStatus.FAILED)
            self._emit(claim_id, PipelineStep.CLAIM_RECEIVED, "claimFailed")
            record = self._store.get_claim(claim_id) or record
            record.status = ClaimStatus.FAILED

        return record

    # --- Individual step implementations ---

    def _step_ingest_document(
        self, claim_id: str, blob_url: str | None
    ) -> dict[str, Any]:
        """Step 2: Document ingestion via DocumentIntelligenceService or stub."""
        self._start_step(claim_id, PipelineStep.INGEST_DOCUMENT)
        try:
            output: dict[str, Any] = {"status": "stub", "note": "Doc Intelligence not called"}
            if blob_url:
                output["blob_url"] = blob_url
            self._complete_step(claim_id, PipelineStep.INGEST_DOCUMENT, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.INGEST_DOCUMENT, str(e))
            return {"status": "failed", "error": str(e)}

    def _step_ingest_images(
        self, claim_id: str, image_urls: list[str]
    ) -> dict[str, Any]:
        """Step 3: Image ingestion via ContentUnderstandingService or stub."""
        self._start_step(claim_id, PipelineStep.INGEST_IMAGES)
        try:
            output: dict[str, Any] = {
                "status": "stub",
                "image_count": len(image_urls),
                "note": "Content Understanding not called",
            }
            self._complete_step(claim_id, PipelineStep.INGEST_IMAGES, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.INGEST_IMAGES, str(e))
            return {"status": "failed", "error": str(e)}

    def _step_ingest_voice(
        self, claim_id: str, audio_url: str | None
    ) -> dict[str, Any]:
        """Step 4: Voice transcription via SpeechService or stub."""
        step = PipelineStep.INGEST_VOICE
        if not audio_url:
            # No audio provided — skip this step
            self._store.update_step(claim_id, step, StepStatus.SKIPPED)
            self._emit(claim_id, step, "stepCompleted", {"skipped": True})
            return {"status": "skipped", "note": "No audio provided"}
        self._start_step(claim_id, step)
        try:
            output: dict[str, Any] = {
                "status": "stub",
                "audio_url": audio_url,
                "note": "Speech STT not called",
            }
            self._complete_step(claim_id, step, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, step, str(e))
            return {"status": "failed", "error": str(e)}

    def _step_classify(self, claim_id: str) -> dict[str, Any]:
        """Step 5: Stub classification."""
        self._start_step(claim_id, PipelineStep.CLASSIFY_STUB)
        self._complete_step(claim_id, PipelineStep.CLASSIFY_STUB, STUB_CLASSIFICATION)
        return STUB_CLASSIFICATION

    def _step_extract_validate(self, claim_id: str) -> dict[str, Any]:
        """Step 6: Stub extraction and validation."""
        self._start_step(claim_id, PipelineStep.EXTRACT_VALIDATE_STUB)
        self._complete_step(
            claim_id, PipelineStep.EXTRACT_VALIDATE_STUB, STUB_EXTRACTION
        )
        return STUB_EXTRACTION

    def _step_decide(self, claim_id: str) -> dict[str, Any]:
        """Step 7: Stub decision."""
        self._start_step(claim_id, PipelineStep.DECIDE_STUB)
        self._complete_step(claim_id, PipelineStep.DECIDE_STUB, STUB_DECISION)
        return STUB_DECISION
