"""Decision reasoning activity — calls DecisionAgent."""

from __future__ import annotations

from typing import Any

from backend.agents.decision_agent import DecisionAgent
from backend.models.claim import AdjudicationDecision


def run_decision(
    classification: dict[str, Any] | None = None,
    extracted_fields: dict[str, Any] | None = None,
    fraud_result: dict[str, Any] | None = None,
    doc_extraction: dict[str, Any] | None = None,
    image_analysis: dict[str, Any] | None = None,
    voice_transcript: dict[str, Any] | None = None,
    evidence_consistency: dict[str, Any] | None = None,
) -> AdjudicationDecision:
    """Run final adjudication via DecisionAgent."""
    agent = DecisionAgent()
    return agent.decide(
        classification=classification,
        extracted_fields=extracted_fields,
        fraud_result=fraud_result,
        doc_extraction=doc_extraction,
        image_analysis=image_analysis,
        voice_transcript=voice_transcript,
        evidence_consistency=evidence_consistency,
    )
