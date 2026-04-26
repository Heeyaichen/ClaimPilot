"""Fraud detection activity — calls FraudDetectionAgent."""

from __future__ import annotations

from typing import Any

from backend.agents.fraud_agent import FraudDetectionAgent
from backend.models.claim import FraudRiskScore


def run_fraud_detection(
    extracted_fields: dict[str, Any] | None = None,
    image_analysis: dict[str, Any] | None = None,
    voice_transcript: dict[str, Any] | None = None,
    classification: dict[str, Any] | None = None,
) -> FraudRiskScore:
    """Run fraud risk assessment via FraudDetectionAgent."""
    agent = FraudDetectionAgent()
    return agent.assess(
        extracted_fields=extracted_fields,
        image_analysis=image_analysis,
        voice_transcript=voice_transcript,
        classification=classification,
    )
