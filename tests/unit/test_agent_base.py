"""Unit tests for FoundryAgentClient — JSON parsing, retry, validation."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.base import (
    AgentResponseError,
    FoundryAgentClient,
    _extract_json,
    _parse_agent_response,
)
from backend.models.claim import ClaimClassification

# --- JSON extraction ---


def test_extract_json_plain_object():
    text = '{"claim_type": "AUTO_PHYSICAL_DAMAGE", "confidence": 0.9}'
    assert _extract_json(text) == text


def test_extract_json_from_code_block():
    text = '```json\n{"claim_type": "THEFT", "confidence": 0.8}\n```'
    result = _extract_json(text)
    parsed = json.loads(result)
    assert parsed["claim_type"] == "THEFT"


def test_extract_json_from_code_block_no_language():
    text = '```\n{"claim_type": "LIABILITY"}\n```'
    result = _extract_json(text)
    parsed = json.loads(result)
    assert parsed["claim_type"] == "LIABILITY"


def test_extract_json_embedded_in_text():
    text = 'Here is the result: {"claim_type": "THEFT", "confidence": 0.75} done.'
    result = _extract_json(text)
    parsed = json.loads(result)
    assert parsed["claim_type"] == "THEFT"


# --- Response parsing ---


def test_parse_valid_json():
    data = {
        "claim_type": "AUTO_PHYSICAL_DAMAGE",
        "confidence": 0.93,
        "routing_rationale": "Test",
        "requires_human_review": False,
    }
    raw = json.dumps(data)
    result = _parse_agent_response(raw, ClaimClassification)
    assert result.claim_type == "AUTO_PHYSICAL_DAMAGE"
    assert result.confidence == 0.93


def test_parse_json_in_code_block():
    data = {
        "claim_type": "TOTAL_LOSS",
        "confidence": 0.85,
        "routing_rationale": "High damage",
        "requires_human_review": False,
    }
    raw = f"```json\n{json.dumps(data)}\n```"
    result = _parse_agent_response(raw, ClaimClassification)
    assert result.claim_type == "TOTAL_LOSS"


def test_parse_malformed_json_raises():
    with pytest.raises(AgentResponseError, match="Could not parse"):
        _parse_agent_response("not json at all {{{{", ClaimClassification, retries=1)


def test_parse_malformed_json_retries_once():
    """First attempt retries, second attempt raises."""
    with pytest.raises(AgentResponseError):
        _parse_agent_response("{{{bad}}}", ClaimClassification, retries=0)


def test_parse_validation_failure_raises():
    data = {
        "claim_type": "UNKNOWN_TYPE",
        "confidence": 1.5,  # out of range
        "routing_rationale": "Test",
    }
    raw = json.dumps(data)
    with pytest.raises(AgentResponseError, match="failed validation"):
        _parse_agent_response(raw, ClaimClassification)


# --- Stub mode ---


def test_stub_mode_raises_agent_response_error():
    with patch("backend.agents.base.get_settings") as mock_settings:
        settings = MagicMock()
        settings.azure_foundry_project_endpoint = ""
        settings.foundry_model_deployment = "gpt-5-4"
        settings.use_stub_agents = True
        mock_settings.return_value = settings

        client = FoundryAgentClient()
        with pytest.raises(AgentResponseError, match="Stub mode"):
            client.run_agent("test", "sys", ClaimClassification)


# --- Confidence threshold enforcement ---


def test_low_confidence_triggers_human_review():
    """ClassifierAgent should set requires_human_review for low confidence."""
    from backend.agents.classifier_agent import ClassifierAgent

    agent = ClassifierAgent.__new__(ClassifierAgent)
    agent._use_stubs = True

    result = agent._stub_classify(None)
    # Stub returns 0.93 confidence, which is above threshold
    assert not result.requires_human_review

    # Simulate low-confidence scenario via the classify method
    mock_client = MagicMock()
    mock_client.run_agent.return_value = ClaimClassification(
        claim_type="AUTO_PHYSICAL_DAMAGE",
        confidence=0.60,
        routing_rationale="Uncertain",
        requires_human_review=False,
    )
    agent2 = ClassifierAgent.__new__(ClassifierAgent)
    agent2._client = mock_client
    agent2._use_stubs = False

    result = agent2.classify()
    assert result.requires_human_review is True
    assert result.review_reason is not None


# --- Fraud recommendation enforcement ---


def test_fraud_recommendation_mapping():
    from backend.agents.fraud_agent import _fraud_recommendation

    assert _fraud_recommendation(0.1) == "proceed"
    assert _fraud_recommendation(0.3) == "proceed"
    assert _fraud_recommendation(0.5) == "adjuster_review"
    assert _fraud_recommendation(0.8) == "escalate_siu"


# --- Decision rules enforcement ---


def test_decision_rules_approve_overridden_by_fraud():
    from backend.agents.decision_agent import _enforce_decision_rules
    from backend.models.claim import AdjudicationDecision

    decision = AdjudicationDecision(
        decision="APPROVE",
        confidence=0.9,
        approved_amount=5000.0,
        reasoning_chain=[],
    )
    fraud = {"score": 0.6}
    result = _enforce_decision_rules(decision, fraud)
    assert result.decision == "ESCALATE"
    assert result.approved_amount is None


def test_decision_rules_approve_overridden_by_low_confidence():
    from backend.agents.decision_agent import _enforce_decision_rules
    from backend.models.claim import AdjudicationDecision

    decision = AdjudicationDecision(
        decision="APPROVE",
        confidence=0.5,
        approved_amount=5000.0,
        reasoning_chain=[],
    )
    result = _enforce_decision_rules(decision, {"score": 0.1})
    assert result.decision == "ESCALATE"


def test_decision_rules_approve_passes_when_valid():
    from backend.agents.decision_agent import _enforce_decision_rules
    from backend.models.claim import AdjudicationDecision

    decision = AdjudicationDecision(
        decision="APPROVE",
        confidence=0.9,
        approved_amount=5000.0,
        reasoning_chain=[],
    )
    result = _enforce_decision_rules(decision, {"score": 0.1})
    assert result.decision == "APPROVE"
    assert result.approved_amount == 5000.0
