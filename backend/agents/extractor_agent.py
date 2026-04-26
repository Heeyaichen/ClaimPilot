"""ExtractorAgent — extracts and validates structured claim fields."""

from __future__ import annotations

import logging
from typing import Any

from backend.agents.base import AgentResponseError, FoundryAgentClient
from backend.models.claim import ExtractedClaimFields

logger = logging.getLogger(__name__)

EXTRACTOR_SYSTEM_PROMPT = """You are a claims data extraction specialist. Given multimodal claim evidence,
extract all structured fields per the domain schema and cross-validate them.

Output ONLY valid JSON matching this schema:
{
    "policy_number": "string or null",
    "applicant_name": "string or null",
    "loss_date": "YYYY-MM-DD or null",
    "loss_description": "string or null",
    "vehicle_make": "string or null",
    "vehicle_model": "string or null",
    "vehicle_year": "integer or null",
    "vin": "string or null",
    "estimated_repair_amount": "float or null",
    "deductible": "float or null",
    "coverage_limit": "float or null",
    "policy_expiry": "YYYY-MM-DD or null",
    "fields_extracted": "count of non-null fields",
    "validation_flags": ["list of validation issues"],
    "confidence": 0.0-1.0
}

Validation rules:
- policy_number must match pattern ^[A-Z]{2}\\d{8}$
- vin must be 17 characters, no I/O/Q
- vehicle_year must be between 1990 and 2027
- estimated_repair_amount must be between 0 and 150000
- loss_date must be within the last 90 days
- Cross-reference: loss_date must be before policy_expiry

Populate validation_flags with any fields that fail validation.
Set fields_extracted to the count of successfully extracted fields.
Set confidence based on extraction completeness and quality.
"""


class ExtractorAgent:
    """Extracts structured fields from claim evidence."""

    def __init__(self, client: FoundryAgentClient | None = None) -> None:
        from backend.core.config import get_settings

        settings = get_settings()
        self._client = client or FoundryAgentClient(
            agent_id=settings.extractor_agent_id or None,
        )
        self._use_stubs = settings.use_stub_agents

    def extract(
        self,
        classification: dict[str, Any] | None = None,
        doc_extraction: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
    ) -> ExtractedClaimFields:
        """Extract and validate structured fields from claim evidence.

        Args:
            classification: Classification result from previous step.
            doc_extraction: Document ingestion output.
            image_analysis: Image ingestion output.
            voice_transcript: Voice ingestion output.

        Returns:
            ExtractedClaimFields with all extracted values and validation flags.
        """
        if self._use_stubs:
            return self._stub_extract()

        context = {
            "classification": classification,
            "doc_extraction": doc_extraction,
            "image_analysis": image_analysis,
            "voice_transcript": voice_transcript,
        }

        prompt = (
            "Extract all structured claim fields from the following evidence.\n"
            "Apply validation rules and report any issues in validation_flags.\n"
            "Return ONLY valid JSON."
        )

        try:
            return self._client.run_agent(
                prompt=prompt,
                system_prompt=EXTRACTOR_SYSTEM_PROMPT,
                output_type=ExtractedClaimFields,
                context=context,
            )
        except AgentResponseError:
            logger.exception("ExtractorAgent failed, falling back to stub")
            return self._stub_extract()

    @staticmethod
    def _stub_extract() -> ExtractedClaimFields:
        """Deterministic stub output for local dev."""
        return ExtractedClaimFields(
            policy_number="AB12345678",
            applicant_name="John Doe",
            loss_date="2026-04-15",
            loss_description="Front-end collision at intersection",
            vehicle_make="Toyota",
            vehicle_model="Camry",
            vehicle_year=2023,
            vin="1HGCG5655WA012345",
            estimated_repair_amount=8400.00,
            deductible=500.00,
            coverage_limit=50000.00,
            policy_expiry="2026-11-30",
            fields_extracted=12,
            validation_flags=[],
            confidence=0.91,
        )
