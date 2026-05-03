"""ClassifierAgent — classifies claim type and routing confidence."""

from __future__ import annotations

import logging
from typing import Any

from backend.agents.base import AgentResponseError, FoundryAgentClient
from backend.models.claim import ClaimClassification

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """You are a claims classification specialist. Given multimodal claim evidence,
you classify the claim type and assess routing confidence.

Output ONLY valid JSON matching this schema:
{
    "claim_type": "AUTO_PHYSICAL_DAMAGE | TOTAL_LOSS | THEFT | LIABILITY",
    "confidence": 0.0-1.0,
    "routing_rationale": "brief explanation",
    "requires_human_review": true/false,
    "review_reason": "null or explanation if requires_human_review is true"
}

Classification rules:
- AUTO_PHYSICAL_DAMAGE: Repairable vehicle damage from collision or incident
- TOTAL_LOSS: Damage estimated > 75% of vehicle ACV, or vehicle not recoverable
- THEFT: Vehicle stolen (partial or complete), without collision
- LIABILITY: Third-party bodily injury or property damage claim

If evidence is insufficient for high-confidence classification (< 0.75),
set requires_human_review to true.
"""

# Domain config classification threshold
CLASSIFICATION_THRESHOLD = 0.75


class ClassifierAgent:
    """Classifies claims by type and determines routing."""

    def __init__(self, client: FoundryAgentClient | None = None) -> None:
        from backend.core.config import get_settings

        settings = get_settings()
        self._client = client or FoundryAgentClient(
            agent_id=settings.classifier_agent_id or None,
        )
        self._use_stubs = settings.use_stub_agents

    def classify(
        self,
        doc_extraction: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
    ) -> ClaimClassification:
        """Run classification on claim evidence.

        Args:
            doc_extraction: Output from document ingestion step.
            image_analysis: Output from image ingestion step.
            voice_transcript: Output from voice ingestion step.

        Returns:
            ClaimClassification with claim_type, confidence, and routing info.
        """
        if self._use_stubs:
            return self._stub_classify(doc_extraction)

        evidence = {
            "doc_extraction": doc_extraction,
            "image_analysis": image_analysis,
            "voice_transcript": voice_transcript,
        }

        prompt = (
            "Classify the following insurance claim based on the provided evidence.\n"
            "Return ONLY valid JSON."
        )

        try:
            result = self._client.run_agent(
                prompt=prompt,
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                output_type=ClaimClassification,
                context=evidence,
            )
        except AgentResponseError:
            if not self._use_stubs:
                raise
            logger.exception("ClassifierAgent failed, falling back to stub")
            return self._stub_classify(doc_extraction)

        # Check confidence threshold
        if result.confidence < CLASSIFICATION_THRESHOLD:
            result.requires_human_review = True
            result.review_reason = (
                f"Classification confidence {result.confidence:.2f} "
                f"below threshold {CLASSIFICATION_THRESHOLD}"
            )

        return result

    @staticmethod
    def _stub_classify(
        doc_extraction: dict[str, Any] | None,
    ) -> ClaimClassification:
        """Deterministic stub output for local dev."""
        return ClaimClassification(
            claim_type="AUTO_PHYSICAL_DAMAGE",
            confidence=0.93,
            routing_rationale="Stub: auto physical damage detected",
            requires_human_review=False,
        )
