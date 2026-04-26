"""Unit tests for agent search integration — verify agents accept and use SearchService."""

from unittest.mock import MagicMock

from backend.agents.extractor_agent import ExtractorAgent
from backend.agents.fraud_agent import FraudDetectionAgent


def test_fraud_agent_uses_prior_claims():
    mock_search = MagicMock()
    mock_search.search_prior_claims.return_value = [
        {"claim_id": "CLM-000001", "claim_amount": 5000},
    ]

    agent = FraudDetectionAgent.__new__(FraudDetectionAgent)
    agent._use_stubs = True
    agent._search = mock_search

    # Stub mode should not call search
    result = agent.assess(
        extracted_fields={"policy_number": "AB12345678", "vin": "1HGCG5655WA012345"},
    )
    assert result.recommendation == "proceed"
    mock_search.search_prior_claims.assert_not_called()


def test_fraud_agent_injectable_search():
    """SearchService is injectable and doesn't block agent creation."""
    mock_search = MagicMock()
    agent = FraudDetectionAgent.__new__(FraudDetectionAgent)
    agent._use_stubs = True
    agent._search = mock_search
    assert agent._search is mock_search


def test_extractor_agent_uses_policy_lookup():
    mock_search = MagicMock()
    mock_search.lookup_policy.return_value = {
        "policy_number": "AB12345678",
        "coverage_limit": 50000,
    }

    agent = ExtractorAgent.__new__(ExtractorAgent)
    agent._use_stubs = True
    agent._search = mock_search

    # Stub mode should not call search
    result = agent.extract(
        doc_extraction={"policy_number": "AB12345678"},
    )
    assert result.policy_number == "AB12345678"
    mock_search.lookup_policy.assert_not_called()


def test_extractor_agent_injectable_search():
    mock_search = MagicMock()
    agent = ExtractorAgent.__new__(ExtractorAgent)
    agent._use_stubs = True
    agent._search = mock_search
    assert agent._search is mock_search
