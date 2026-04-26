"""Extraction activity — calls ExtractorAgent."""

from __future__ import annotations

from typing import Any

from backend.agents.extractor_agent import ExtractorAgent
from backend.models.claim import ExtractedClaimFields


def run_extraction(
    classification: dict[str, Any] | None = None,
    doc_extraction: dict[str, Any] | None = None,
    image_analysis: dict[str, Any] | None = None,
    voice_transcript: dict[str, Any] | None = None,
) -> ExtractedClaimFields:
    """Run field extraction and validation via ExtractorAgent."""
    agent = ExtractorAgent()
    return agent.extract(
        classification=classification,
        doc_extraction=doc_extraction,
        image_analysis=image_analysis,
        voice_transcript=voice_transcript,
    )
