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

from backend.agents.base import AgentResponseError
from backend.core.config import get_settings
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
        self._settings = get_settings()
        self._use_stubs = self._settings.use_stub_agents

        # Lazy-initialized service instances
        self._doc_intel_service = None
        self._content_understanding_service = None
        self._foundry_vision_service = None
        self._speech_service = None
        self._blob_service = None

    def _get_doc_intel_service(self):
        if self._doc_intel_service is None:
            from backend.services.document_intelligence import DocumentIntelligenceService
            self._doc_intel_service = DocumentIntelligenceService()
        return self._doc_intel_service

    def _get_content_understanding_service(self):
        if self._content_understanding_service is None:
            from backend.services.content_understanding import ContentUnderstandingService
            self._content_understanding_service = ContentUnderstandingService()
        return self._content_understanding_service

    def _get_foundry_vision_service(self):
        if self._foundry_vision_service is None:
            from backend.services.foundry_vision import FoundryVisionService
            self._foundry_vision_service = FoundryVisionService()
        return self._foundry_vision_service

    def _get_speech_service(self):
        if self._speech_service is None:
            from backend.services.speech import SpeechService
            self._speech_service = SpeechService()
        return self._speech_service

    def _get_blob_service(self):
        if self._blob_service is None:
            from backend.services.blob_storage import BlobStorageService
            self._blob_service = BlobStorageService()
        return self._blob_service

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

    async def run_pipeline(self, record: ClaimRecord) -> ClaimRecord:
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
            doc_output = await self._step_ingest_document(claim_id, record.form_blob_url)
            image_output = await self._step_ingest_images(claim_id, record.image_blob_urls)
            voice_output = await self._step_ingest_voice(claim_id, record.audio_blob_url)

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

        except AgentResponseError as e:
            # Agent failures (rate limit, API error) → ESCALATE, not FAIL
            logger.exception("Agent error for claim %s: %s", claim_id, e)
            record = self._store.get_claim(claim_id) or record
            record.status = ClaimStatus.ESCALATED
            record.updated_at = datetime.utcnow()
            # Ensure decision_result exists with escalation reason
            if not record.decision_result:
                record.decision_result = {
                    "decision": "ESCALATE",
                    "confidence": 0.0,
                    "escalation_reason": str(e),
                    "rejection_reason": None,
                    "approved_amount": None,
                    "reasoning_chain": [
                        {
                            "step": "Agent error",
                            "conclusion": "Pipeline agent unavailable",
                            "evidence_source": "system",
                            "evidence_value": str(e),
                        }
                    ],
                }
            self._store.mark_claim_status(claim_id, ClaimStatus.ESCALATED)
            self._emit(
                claim_id, PipelineStep.DECIDE, "claimDecided",
                {"outcome": "ESCALATED", "reason": str(e)},
            )
        except Exception:
            logger.exception("Pipeline failed for claim %s", claim_id)
            record = self._store.get_claim(claim_id) or record
            record.status = ClaimStatus.ESCALATED
            record.updated_at = datetime.utcnow()
            if not record.decision_result:
                record.decision_result = {
                    "decision": "ESCALATE",
                    "confidence": 0.0,
                    "escalation_reason": "Pipeline error — adjuster review required",
                    "rejection_reason": None,
                    "approved_amount": None,
                    "reasoning_chain": [],
                }
            self._store.mark_claim_status(claim_id, ClaimStatus.ESCALATED)
            self._emit(
                claim_id, PipelineStep.DECIDE, "claimDecided",
                {"outcome": "ESCALATED", "reason": "Pipeline error"},
            )

        return record

    # --- Individual step implementations ---

    async def _step_ingest_document(
        self, claim_id: str, blob_url: str | None
    ) -> dict[str, Any]:
        """Step 2: Document ingestion via Azure Document Intelligence."""
        self._start_step(claim_id, PipelineStep.INGEST_DOCUMENT)
        try:
            if self._use_stubs:
                output: dict[str, Any] = {"status": "stub", "note": "Doc Intelligence not called (stub mode)"}
                if blob_url:
                    output["blob_url"] = blob_url
                self._complete_step(claim_id, PipelineStep.INGEST_DOCUMENT, output)
                return output

            if not blob_url:
                output = {"status": "completed", "note": "No form document provided"}
                self._complete_step(claim_id, PipelineStep.INGEST_DOCUMENT, output)
                return output

            service = self._get_doc_intel_service()
            result = await service.extract_claim_form(blob_url)
            output = result.model_dump()
            output["status"] = "completed"
            output["blob_url"] = blob_url
            self._complete_step(claim_id, PipelineStep.INGEST_DOCUMENT, output)
            return output
        except Exception as e:
            self._fail_step(claim_id, PipelineStep.INGEST_DOCUMENT, str(e))
            return {"status": "failed", "error": str(e)}

    async def _step_ingest_images(
        self, claim_id: str, image_urls: list[str]
    ) -> dict[str, Any]:
        """Step 3: Image ingestion via configured provider (CU or Foundry Vision)."""
        self._start_step(claim_id, PipelineStep.INGEST_IMAGES)
        try:
            if self._use_stubs:
                output: dict[str, Any] = {
                    "status": "stub",
                    "image_count": len(image_urls),
                    "note": "Image analysis not called (stub mode)",
                }
                self._complete_step(claim_id, PipelineStep.INGEST_IMAGES, output)
                return output

            if not image_urls:
                output = {"status": "completed", "image_count": 0}
                self._complete_step(claim_id, PipelineStep.INGEST_IMAGES, output)
                return output

            provider = self._settings.image_analysis_provider

            if provider == "disabled":
                output = {
                    "status": "completed",
                    "image_count": len(image_urls),
                    "note": "Image analysis disabled by configuration",
                }
                self._complete_step(claim_id, PipelineStep.INGEST_IMAGES, output)
                return output

            # Try configured provider, fall back to vision if CU fails
            service = None
            actual_provider = provider
            if provider == "foundry_vision":
                service = self._get_foundry_vision_service()
            else:
                # Default: try CU first, fall back to Foundry Vision
                try:
                    service = self._get_content_understanding_service()
                    actual_provider = "content_understanding"
                except Exception:
                    service = None

                if service is None:
                    service = self._get_foundry_vision_service()
                    actual_provider = "foundry_vision"

            # Try analysis with selected service
            try:
                all_damage_indicators: list[dict[str, Any]] = []
                all_forensic_flags: list[str] = []
                image_results: list[dict[str, Any]] = []

                for url in image_urls:
                    img_result = await service.analyze_accident_image(url)
                    result_dict = img_result.model_dump()
                    image_results.append(result_dict)
                    all_damage_indicators.extend(
                        d if isinstance(d, dict) else d
                        for d in result_dict.get("damage_indicators", [])
                    )
                    all_forensic_flags.extend(result_dict.get("forensic_flags", []))

                output = {
                    "status": "completed",
                    "image_count": len(image_urls),
                    "provider": actual_provider,
                    "damage_indicators": all_damage_indicators,
                    "forensic_flags": all_forensic_flags,
                    "image_results": image_results,
                }
                self._complete_step(claim_id, PipelineStep.INGEST_IMAGES, output)
                return output
            except Exception as e:
                # CU failed — try Foundry Vision fallback
                if actual_provider == "content_understanding":
                    logger.warning(
                        "CU image analysis failed (%s), trying Foundry Vision fallback",
                        e,
                    )
                    try:
                        service = self._get_foundry_vision_service()
                        all_damage_indicators = []
                        all_forensic_flags = []
                        image_results = []

                        for url in image_urls:
                            img_result = await service.analyze_accident_image(url)
                            result_dict = img_result.model_dump()
                            image_results.append(result_dict)
                            all_damage_indicators.extend(
                                d if isinstance(d, dict) else d
                                for d in result_dict.get("damage_indicators", [])
                            )
                            all_forensic_flags.extend(
                                result_dict.get("forensic_flags", [])
                            )

                        output = {
                            "status": "completed",
                            "image_count": len(image_urls),
                            "provider": "foundry_vision",
                            "damage_indicators": all_damage_indicators,
                            "forensic_flags": all_forensic_flags,
                            "image_results": image_results,
                        }
                        self._complete_step(
                            claim_id, PipelineStep.INGEST_IMAGES, output
                        )
                        return output
                    except Exception as fallback_err:
                        raise RuntimeError(
                            f"Image analysis failed: CU error ({e}), "
                            f"Vision fallback error ({fallback_err})"
                        ) from fallback_err
                raise

        except Exception as e:
            self._fail_step(claim_id, PipelineStep.INGEST_IMAGES, str(e))
            return {"status": "failed", "image_count": len(image_urls), "error": str(e)}

    async def _step_ingest_voice(
        self, claim_id: str, audio_url: str | None
    ) -> dict[str, Any]:
        """Step 4: Voice transcription via Azure Speech."""
        step = PipelineStep.INGEST_VOICE
        if not audio_url:
            self._store.update_step(claim_id, step, StepStatus.SKIPPED)
            self._emit(claim_id, step, "stepCompleted", {"skipped": True})
            return {"status": "skipped", "note": "No audio provided"}
        self._start_step(claim_id, step)
        try:
            if self._use_stubs:
                output: dict[str, Any] = {
                    "status": "stub",
                    "audio_url": audio_url,
                    "note": "Speech STT not called (stub mode)",
                }
                self._complete_step(claim_id, step, output)
                return output

            # Download blob to temp file — SpeechService requires local paths
            blob_service = self._get_blob_service()
            temp_path = blob_service.download_blob_to_temp(audio_url)
            try:
                service = self._get_speech_service()
                result = await service.transcribe_voice_statement(temp_path)
                output = result.model_dump()
                output["status"] = "completed"
                output["audio_url"] = audio_url
            finally:
                import os
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

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
