"""FraudDetectionAgent — multi-signal fraud risk assessment."""

from __future__ import annotations

import logging
import typing
from typing import Any

from backend.agents.base import AgentResponseError, FoundryAgentClient
from backend.models.claim import FraudRiskScore

if typing.TYPE_CHECKING:
    from backend.services.search import SearchService

logger = logging.getLogger(__name__)

FRAUD_SYSTEM_PROMPT = """You are a fraud detection specialist for auto insurance claims.
Analyze the provided claim evidence across multiple signals and produce
a fraud risk assessment.

Evidence signals available to you:
1. Document fields (from ACORD form extraction)
2. Image forensic analysis (from Content Understanding)
3. Voice statement transcript with sentiment markers
4. Extraction validation flags

Fraud indicators to check:
- Damage pattern inconsistency: Does image damage match the stated accident type?
- Timeline inconsistency: Claimed date vs. vehicle condition in photos
- Coverage timing: Was the policy taken out recently before the loss?
- Statement inconsistency: Voice transcript contradicts written form
- Total loss pattern: Older vehicle, high mileage, full comprehensive claim
- Amount anomaly: Repair estimate unusually high for stated damage

Scoring guidance:
- 0.0-0.3: Low risk — proceed to automated decision
- 0.3-0.7: Medium risk — flag for adjuster review (do not block)
- 0.7-1.0: High risk — escalate to Special Investigations Unit

Output ONLY valid JSON matching this schema:
{
    "score": 0.0-1.0,
    "signals": {
        "damage_consistency": 0.0-1.0,
        "timeline_consistency": 0.0-1.0,
        "coverage_timing": 0.0-1.0,
        "statement_consistency": 0.0-1.0,
        "amount_reasonableness": 0.0-1.0
    },
    "flags": ["list of anomaly descriptions"],
    "recommendation": "proceed | adjuster_review | escalate_siu"
}

Recommendation rules:
- score < 0.4: "proceed"
- 0.4 <= score < 0.7: "adjuster_review"
- score >= 0.7: "escalate_siu"
"""

# Thresholds from domain config
FRAUD_LOW = 0.4
FRAUD_HIGH = 0.7


class FraudDetectionAgent:
    """Analyzes claim evidence for fraud risk signals."""

    def __init__(
        self,
        client: FoundryAgentClient | None = None,
        search_service: SearchService | None = None,
    ) -> None:
        from backend.core.config import get_settings

        settings = get_settings()
        self._client = client or FoundryAgentClient(
            agent_id=settings.fraud_agent_id or None,
        )
        self._use_stubs = settings.use_stub_agents
        self._search = search_service

    def assess(
        self,
        extracted_fields: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
        classification: dict[str, Any] | None = None,
    ) -> FraudRiskScore:
        """Run multi-signal fraud risk assessment.

        Args:
            extracted_fields: Output from extractor agent.
            image_analysis: Image ingestion output.
            voice_transcript: Voice ingestion output.
            classification: Classification result.

        Returns:
            FraudRiskScore with risk score, signals, and recommendation.
        """
        if self._use_stubs:
            return self._stub_assess()

        context: dict[str, Any] = {
            "extracted_fields": extracted_fields,
            "image_analysis": image_analysis,
            "voice_transcript": voice_transcript,
            "classification": classification,
        }

        # Enrich with prior claims from Azure Search
        if self._search and extracted_fields:
            prior_claims = self._search.search_prior_claims(
                policy_number=extracted_fields.get("policy_number"),
                vin=extracted_fields.get("vin"),
                policy_holder_name=extracted_fields.get("applicant_name"),
            )
            if prior_claims:
                context["prior_claims"] = prior_claims

        prompt = (
            "Analyze the following claim evidence for fraud risk indicators.\n"
            "Return ONLY valid JSON."
        )

        try:
            result = self._client.run_agent(
                prompt=prompt,
                system_prompt=FRAUD_SYSTEM_PROMPT,
                output_type=FraudRiskScore,
                context=context,
            )
        except AgentResponseError:
            if not self._use_stubs:
                raise
            logger.exception("FraudDetectionAgent failed, falling back to stub")
            return self._stub_assess()

        # Enforce recommendation consistency with thresholds
        result.recommendation = _fraud_recommendation(result.score)

        return result

    @staticmethod
    def _stub_assess() -> FraudRiskScore:
        """Deterministic stub output for local dev."""
        return FraudRiskScore(
            score=0.18,
            signals={
                "damage_consistency": 0.1,
                "timeline_consistency": 0.1,
                "coverage_timing": 0.2,
                "statement_consistency": 0.1,
                "amount_reasonableness": 0.3,
            },
            flags=[],
            recommendation="proceed",
        )


def _fraud_recommendation(score: float) -> str:
    """Map fraud score to recommendation based on domain thresholds."""
    if score >= FRAUD_HIGH:
        return "escalate_siu"
    if score >= FRAUD_LOW:
        return "adjuster_review"
    return "proceed"
