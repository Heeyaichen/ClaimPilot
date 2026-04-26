"""Unit tests for ClaimLookupTool."""

from unittest.mock import MagicMock

from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)
from backend.services.claim_lookup_tool import ClaimLookupTool


def _mock_store(claim_id: str = "c1") -> MagicMock:
    """Create a mock ClaimStateStore with a sample processed claim."""
    record = ClaimRecord(
        claim_id=claim_id,
        status=ClaimStatus.APPROVED,
        claimant_name="Jane Smith",
        policy_number="POL-001",
        steps=[PipelineStepState(step=PipelineStep.DECIDE, status=StepStatus.COMPLETED)],
        fraud_result={"score": 0.18, "flags": [], "recommendation": "proceed"},
        decision_result={
            "decision": "APPROVE",
            "confidence": 0.92,
            "approved_amount": 8400.0,
            "reasoning_chain": [
                {"step": "Coverage check", "conclusion": "Policy active"},
                {"step": "Fraud screen", "conclusion": "Low risk"},
            ],
        },
        doc_extraction={"policy_number": "POL-001", "summary": "ACORD form extracted"},
        image_analysis={"summary": "Front bumper damage, moderate severity"},
    )
    store = MagicMock()
    store.get_claim.return_value = record
    return store


def _mock_store_not_found() -> MagicMock:
    store = MagicMock()
    store.get_claim.return_value = None
    return store


def test_get_claim_summary_found():
    tool = ClaimLookupTool(state_store=_mock_store())
    result = tool.get_claim_summary("c1")
    assert result.found is True
    assert "APPROVE" in result.summary
    assert result.decision == "APPROVE"
    assert result.approved_amount == 8400.0


def test_get_claim_summary_not_found():
    tool = ClaimLookupTool(state_store=_mock_store_not_found())
    result = tool.get_claim_summary("c1")
    assert result.found is False
    assert "not found" in result.error


def test_get_fraud_score():
    tool = ClaimLookupTool(state_store=_mock_store())
    result = tool.get_fraud_score("c1")
    assert result.found is True
    assert result.fraud_score == 0.18
    assert "0.18" in result.summary


def test_get_damage_assessment():
    tool = ClaimLookupTool(state_store=_mock_store())
    result = tool.get_damage_assessment("c1")
    assert result.found is True
    assert result.damage_assessment is not None
    assert "Front bumper" in result.damage_assessment


def test_get_decision_reasoning():
    tool = ClaimLookupTool(state_store=_mock_store())
    result = tool.get_decision_reasoning("c1")
    assert result.found is True
    assert "Coverage check" in result.summary
    assert "Fraud screen" in result.summary


def test_get_decision_reasoning_no_chain():
    store = _mock_store()
    record = store.get_claim.return_value
    record.decision_result = {"decision": "APPROVE"}
    tool = ClaimLookupTool(state_store=store)
    result = tool.get_decision_reasoning("c1")
    assert result.found is True
    assert "No reasoning chain" in result.summary


def test_as_tool_definitions():
    tool = ClaimLookupTool(state_store=_mock_store())
    defs = tool.as_tool_definitions()
    assert len(defs) == 4
    names = [d["function"]["name"] for d in defs]
    assert "get_claim_summary" in names
    assert "get_fraud_score" in names
    assert "get_damage_assessment" in names
    assert "get_decision_reasoning" in names


def test_handle_tool_call_dispatch():
    tool = ClaimLookupTool(state_store=_mock_store())
    result = tool.handle_tool_call("get_fraud_score", {"claim_id": "c1"})
    assert result.found is True
    assert result.fraud_score == 0.18


def test_handle_tool_call_unknown():
    tool = ClaimLookupTool(state_store=_mock_store())
    result = tool.handle_tool_call("nonexistent_tool", {"claim_id": "c1"})
    assert result.found is False
    assert "Unknown tool" in result.error


def test_no_state_store():
    tool = ClaimLookupTool(state_store=None)
    result = tool.get_claim_summary("c1")
    assert result.found is False
