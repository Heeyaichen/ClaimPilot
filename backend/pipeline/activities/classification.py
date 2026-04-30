"""Classification activity — calls ClassifierAgent."""

from __future__ import annotations

from typing import Any

from backend.agents.classifier_agent import ClassifierAgent
from backend.models.claim import ClaimClassification


def run_classification(
    doc_extraction: dict[str, Any] | None = None,
    image_analysis: dict[str, Any] | None = None,
    voice_transcript: dict[str, Any] | None = None,
) -> ClaimClassification:
    """Run claim classification via ClassifierAgent."""
    agent = ClassifierAgent()
    return agent.classify(
        doc_extraction=doc_extraction,
        image_analysis=image_analysis,
        voice_transcript=voice_transcript,
    )
