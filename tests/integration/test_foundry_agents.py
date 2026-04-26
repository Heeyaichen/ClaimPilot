"""Integration tests for Foundry Agent Service — skipped unless RUN_AZURE_INTEGRATION=1."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AZURE_INTEGRATION") != "1",
    reason="Set RUN_AZURE_INTEGRATION=1 to run live Azure integration tests",
)


def test_classifier_agent_live():
    """Live test: ClassifierAgent classifies a claim via Foundry."""
    from backend.agents.classifier_agent import ClassifierAgent

    agent = ClassifierAgent()
    result = agent.classify(
        doc_extraction={"status": "stub"},
        image_analysis={"status": "stub", "image_count": 2},
        voice_transcript=None,
    )
    assert result.claim_type in (
        "AUTO_PHYSICAL_DAMAGE",
        "TOTAL_LOSS",
        "THEFT",
        "LIABILITY",
    )
    assert 0.0 <= result.confidence <= 1.0


def test_extractor_agent_live():
    """Live test: ExtractorAgent extracts fields via Foundry."""
    from backend.agents.extractor_agent import ExtractorAgent

    agent = ExtractorAgent()
    result = agent.extract(
        classification={"claim_type": "AUTO_PHYSICAL_DAMAGE"},
        doc_extraction={"status": "stub"},
    )
    assert result.confidence > 0.0
    assert isinstance(result.validation_flags, list)


def test_fraud_agent_live():
    """Live test: FraudDetectionAgent scores fraud risk via Foundry."""
    from backend.agents.fraud_agent import FraudDetectionAgent

    agent = FraudDetectionAgent()
    result = agent.assess(
        extracted_fields={"policy_number": "AB12345678"},
    )
    assert 0.0 <= result.score <= 1.0
    assert result.recommendation in ("proceed", "adjuster_review", "escalate_siu")


def test_decision_agent_live():
    """Live test: DecisionAgent produces adjudication via Foundry."""
    from backend.agents.decision_agent import DecisionAgent

    agent = DecisionAgent()
    result = agent.decide(
        classification={"claim_type": "AUTO_PHYSICAL_DAMAGE", "confidence": 0.93},
        extracted_fields={"policy_number": "AB12345678", "estimated_repair_amount": 8400},
        fraud_result={"score": 0.18, "recommendation": "proceed"},
    )
    assert result.decision in ("APPROVE", "REJECT", "ESCALATE")
    assert len(result.reasoning_chain) > 0
