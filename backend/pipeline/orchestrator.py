"""Claim processing orchestrator — Durable Functions pattern.

Implements the 8-step claim pipeline:
1. CLAIM_RECEIVED — validate input, mark received
2-4. INGEST_DOCUMENT, INGEST_IMAGES, INGEST_VOICE — fan-out in parallel
5. CLASSIFY — ClassifierAgent determines claim type
6. EXTRACT_VALIDATE — ExtractorAgent extracts and validates fields
7. FRAUD_SCREENING — FraudDetectionAgent assesses fraud risk
8. DECIDE — DecisionAgent produces traceable adjudication

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
from backend.pipeline.activities.classification import run_classification
from backend.pipeline.activities.extraction import run_extraction
from backend.pipeline.activities.fraud_detection import run_fraud_detection
from backend.pipeline.activities.reasoning import run_decision
from backend.services.claim_state_store import ClaimStateStore
from backend.services.evidence_validator import validate_evidence
from backend.services.signalr import SignalRBroadcaster

logger = logging.getLogger(__name__)


class ClaimOrchestrator:
    """Orchestrates the 8-step claim processing pipeline.

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
        """Execute the full 8-step pipeline for a claim.

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
            # executed sequentially here; Durable Functions fan_out/fan_in
            # handles true parallelism in production)
            doc_output = self._step_ingest_document(claim_id, record.form_blob_url)
            image_output = self._step_ingest_images(claim_id, record.image_blob_urls)
            voice_output = self._step_ingest_voice(claim_id, record.audio_blob_url)

            # Step 5: CLASSIFY
            classify_output = self._step_classify(
                claim_id,
                doc_extraction=doc_output,
                image_analysis=image_output,
                voice_transcript=voice_output,
            )

            # Step 6: EXTRACT_VALIDATE
            extract_output = self._step_extract_validate(
                claim_id,
                classification=classify_output,
                doc_extraction=doc_output,
                image_analysis=image_output,
                voice_transcript=voice_output,
            )

            # Evidence consistency validation
            evidence_result = validate_evidence(
                claimant_name_submitted=record.claimant_name,
                policy_number_submitted=record.policy_number,
                extracted_fields=extract_output,
            )
            evidence_output = evidence_result.model_dump()
            self._store.update_step(
                claim_id,
                PipelineStep.EXTRACT_VALIDATE,
                StepStatus.COMPLETED,
                output={**extract_output, "evidence_consistency": evidence_output},
            )

            # Step 7: FRAUD_SCREENING
            fraud_output = self._step_fraud_screening(
                claim_id,
                extracted_fields=extract_output,
                image_analysis=image_output,
                voice_transcript=voice_output,
                classification=classify_output,
            )

            # Step 8: DECIDE
            decision_output = self._step_decide(
                claim_id,
                classification=classify_output,
                extracted_fields=extract_output,
                fraud_result=fraud_output,
                doc_extraction=doc_output,
                image_analysis=image_output,
                voice_transcript=voice_output,
                evidence_consistency=evidence_output,
            )

            # Update final record
            record = self._store.get_claim(claim_id) or record
            record.doc_extraction = doc_output
            record.image_analysis = image_output
            record.voice_transcript = voice_output
            record.classification_result = classify_output
            record.extraction_result = extract_output
            record.fraud_result = fraud_output
            record.decision_result = decision_output
            record.evidence_consistency = evidence_output

            # Map decision to claim status
            decision = decision_output.get("decision", "ESCALATE")
            if decision == "APPROVE":
                record.status = ClaimStatus.APPROVED
            elif decision == "REJECT":
                record.status = ClaimStatus.REJECTED
            else:
                record.status = ClaimStatus.ESCALATED

            record.updated_at = datetime.utcnow()
            record.pipeline_duration_seconds = (
                record.updated_at - record.submitted_at
            ).total_seconds()
            self._store.mark_claim_status(claim_id, record.status)

            self._emit(
                claim_id,
                PipelineStep.DECIDE,
                "claimDecided",
                {"outcome": record.status.value},
            )
            logger.info("Pipeline completed for claim %s → %s", claim_id, record.status.value)

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
        """Step 2: Document ingestion."""
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
        """Step 3: Image ingestion."""
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
        """Step 4: Voice transcription."""
        step = PipelineStep.INGEST_VOICE
        if not audio_url:
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

    def _step_classify(
        self,
        claim_id: str,
        doc_extraction: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 5: Classification via ClassifierAgent."""
        self._start_step(claim_id, PipelineStep.CLASSIFY)
        try:
            result = run_classification(
                doc_extraction=doc_extraction,
                image_analysis=image_analysis,
                voice_transcript=voice_transcript,
            )
            output = result.model_dump()
            self._complete_step(claim_id, PipelineStep.CLASSIFY, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.CLASSIFY, str(e))
            raise

    def _step_extract_validate(
        self,
        claim_id: str,
        classification: dict[str, Any] | None = None,
        doc_extraction: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 6: Extraction and validation via ExtractorAgent."""
        self._start_step(claim_id, PipelineStep.EXTRACT_VALIDATE)
        try:
            result = run_extraction(
                classification=classification,
                doc_extraction=doc_extraction,
                image_analysis=image_analysis,
                voice_transcript=voice_transcript,
            )
            output = result.model_dump()
            self._complete_step(claim_id, PipelineStep.EXTRACT_VALIDATE, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.EXTRACT_VALIDATE, str(e))
            raise

    def _step_fraud_screening(
        self,
        claim_id: str,
        extracted_fields: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
        classification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 7: Fraud risk assessment via FraudDetectionAgent."""
        self._start_step(claim_id, PipelineStep.FRAUD_SCREENING)
        try:
            result = run_fraud_detection(
                extracted_fields=extracted_fields,
                image_analysis=image_analysis,
                voice_transcript=voice_transcript,
                classification=classification,
            )
            output = result.model_dump()
            self._complete_step(claim_id, PipelineStep.FRAUD_SCREENING, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.FRAUD_SCREENING, str(e))
            raise

    def _step_decide(
        self,
        claim_id: str,
        classification: dict[str, Any] | None = None,
        extracted_fields: dict[str, Any] | None = None,
        fraud_result: dict[str, Any] | None = None,
        doc_extraction: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
        evidence_consistency: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 8: Final decision via DecisionAgent."""
        self._start_step(claim_id, PipelineStep.DECIDE)
        try:
            result = run_decision(
                classification=classification,
                extracted_fields=extracted_fields,
                fraud_result=fraud_result,
                doc_extraction=doc_extraction,
                image_analysis=image_analysis,
                voice_transcript=voice_transcript,
                evidence_consistency=evidence_consistency,
            )
            output = result.model_dump()
            self._complete_step(claim_id, PipelineStep.DECIDE, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.DECIDE, str(e))
            raise
