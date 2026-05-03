"""Unit tests for evidence consistency validation."""

from __future__ import annotations

from backend.agents.decision_agent import _enforce_decision_rules
from backend.models.claim import AdjudicationDecision, ClaimRecord
from backend.services.evidence_validator import (
    _is_gibberish,
    _is_name_gibberish,
    _is_valid_policy_number,
    _names_match,
    lookup_policy,
    validate_evidence,
)

# --- Validator unit tests ---


class TestNameNormalization:
    def test_names_match_exact(self) -> None:
        assert _names_match("Maria Thompson", "Maria Thompson")

    def test_names_match_case_insensitive(self) -> None:
        assert _names_match("maria thompson", "MARIA THOMPSON")

    def test_names_match_extra_whitespace(self) -> None:
        assert _names_match("Maria  Thompson", " Maria Thompson ")

    def test_names_no_match(self) -> None:
        assert not _names_match("Maria Thompson", "James Chen")


class TestGibberishDetection:
    def test_empty_is_gibberish(self) -> None:
        assert _is_gibberish("")

    def test_whitespace_is_gibberish(self) -> None:
        assert _is_gibberish("   ")

    def test_valid_name_not_gibberish(self) -> None:
        assert not _is_name_gibberish("Maria Thompson")

    def test_single_letter_gibberish(self) -> None:
        assert _is_name_gibberish("a")

    def test_numbers_only_gibberish(self) -> None:
        assert _is_name_gibberish("123456")

    def test_random_chars_not_caught_by_basic_check(self) -> None:
        """8 alphabetic chars passes basic check — caught by policy lookup mismatch instead."""
        assert not _is_name_gibberish("asdfqwer")


class TestPolicyNumberFormat:
    def test_valid_policy(self) -> None:
        assert _is_valid_policy_number("AT42093871")

    def test_invalid_too_short(self) -> None:
        assert not _is_valid_policy_number("AT123")

    def test_invalid_wrong_format(self) -> None:
        assert not _is_valid_policy_number("42093871AT")

    def test_invalid_lowercase(self) -> None:
        assert not _is_valid_policy_number("at42093871")


class TestPolicyLookup:
    def test_known_policies_found(self) -> None:
        assert lookup_policy("AT42093871") is not None
        assert lookup_policy("JC77120456") is not None
        assert lookup_policy("DB55309128") is not None

    def test_unknown_policy_not_found(self) -> None:
        assert lookup_policy("ZZ99999999") is None

    def test_policy_holder_names(self) -> None:
        assert lookup_policy("AT42093871")["policy_holder_name"] == "Maria Thompson"
        assert lookup_policy("JC77120456")["policy_holder_name"] == "James Chen"
        assert lookup_policy("DB55309128")["policy_holder_name"] == "Diana Brooks"


class TestValidationHappyPath:
    """claim_001_approve: Maria Thompson, AT42093871 → no errors."""

    def test_valid_claim_no_errors(self) -> None:
        result = validate_evidence("Maria Thompson", "AT42093871")
        assert result.validation_errors == []
        assert result.escalation_reasons == []
        assert result.name_match is True
        assert result.policy_lookup_status == "found"
        assert result.confidence >= 0.9

    def test_valid_claim_with_matching_extraction(self) -> None:
        result = validate_evidence(
            "Maria Thompson",
            "AT42093871",
            {"applicant_name": "Maria Thompson", "policy_number": "AT42093871"},
        )
        assert result.validation_errors == []
        assert result.name_match is True
        assert result.policy_match is True
        assert result.form_matches_submission is True


class TestValidationGibberish:
    def test_gibberish_name_escalates(self) -> None:
        result = validate_evidence("asdfghjkl", "AT42093871")
        assert len(result.validation_errors) > 0
        assert result.escalation_reasons != []

    def test_empty_name_escalates(self) -> None:
        result = validate_evidence("", "AT42093871")
        assert "Submitted claimant name is empty" in result.validation_errors

    def test_gibberish_policy_escalates(self) -> None:
        result = validate_evidence("Maria Thompson", "ZZ99999999")
        assert len(result.validation_errors) > 0
        assert "Policy not found" in result.validation_errors[0]


class TestValidationMismatch:
    def test_name_mismatch_with_extracted(self) -> None:
        result = validate_evidence(
            "James Chen",
            "AT42093871",
            {"applicant_name": "Maria Thompson"},
        )
        assert any("mismatch" in e.lower() for e in result.validation_errors)

    def test_policy_mismatch_with_extracted(self) -> None:
        result = validate_evidence(
            "Maria Thompson",
            "AT42093871",
            {"policy_number": "JC77120456"},
        )
        assert any("Policy number mismatch" in e for e in result.validation_errors)

    def test_claimant_not_policy_holder(self) -> None:
        result = validate_evidence("James Chen", "AT42093871")
        assert any("Policy holder mismatch" in e for e in result.validation_errors)

    def test_mixed_claim_data_escalates(self) -> None:
        """claim_001 form + claim_002 submitted metadata → escalate."""
        result = validate_evidence(
            "James Chen",  # claim_002 claimant
            "JC77120456",  # claim_002 policy
            {"applicant_name": "Maria Thompson", "policy_number": "AT42093871"},
        )
        assert len(result.validation_errors) > 0


class TestValidationDemoScenarios:
    """Verify expected outcomes for all three demo claim bundles."""

    def test_claim_001_approve_passes(self) -> None:
        result = validate_evidence("Maria Thompson", "AT42093871")
        assert result.validation_errors == []

    def test_claim_002_escalate_still_validates_clean(self) -> None:
        """claim_002 has a valid policy — escalation happens via fraud score."""
        result = validate_evidence("James Chen", "JC77120456")
        assert result.validation_errors == []
        assert result.name_match is True

    def test_claim_003_fraud_review_still_validates_clean(self) -> None:
        """claim_003 has a valid policy — fraud review happens via fraud signals."""
        result = validate_evidence("Diana Brooks", "DB55309128")
        assert result.validation_errors == []
        assert result.name_match is True

    def test_mixed_001_form_002_submitted_escalates(self) -> None:
        """form from 001, submitted data from 002 → escalation."""
        result = validate_evidence(
            "James Chen",
            "JC77120456",
            {"applicant_name": "Maria Thompson", "policy_number": "AT42093871"},
        )
        assert len(result.validation_errors) >= 2  # both name and policy mismatch


class TestValidationWithRealExtraction:
    """Tests for behavior with real (non-stub) extracted fields."""

    def test_real_extracted_name_mismatch_escalates(self) -> None:
        """Real extraction that doesn't match submitted name → escalation."""
        result = validate_evidence(
            "James Chen",
            "AT42093871",
            {"applicant_name": "Maria Thompson"},
        )
        assert any("mismatch" in e.lower() for e in result.validation_errors)
        assert result.name_match is False

    def test_real_extracted_policy_mismatch_escalates(self) -> None:
        """Real extraction that doesn't match submitted policy → escalation."""
        result = validate_evidence(
            "Maria Thompson",
            "AT42093871",
            {"policy_number": "JC77120456"},
        )
        assert any("Policy number mismatch" in e for e in result.validation_errors)
        assert result.policy_match is False

    def test_no_extracted_fields_skips_comparison(self) -> None:
        """When extraction returns no fields (stub mode or empty), comparison is skipped."""
        result = validate_evidence("Maria Thompson", "AT42093871", {})
        assert result.validation_errors == []

    def test_none_extracted_fields_skips_comparison(self) -> None:
        """None extracted_fields → comparison is skipped."""
        result = validate_evidence("Maria Thompson", "AT42093871", None)
        assert result.validation_errors == []

    def test_extracted_fields_match_no_errors(self) -> None:
        """Extracted fields match submitted → no errors, matches confirmed."""
        result = validate_evidence(
            "Maria Thompson",
            "AT42093871",
            {"applicant_name": "Maria Thompson", "policy_number": "AT42093871"},
        )
        assert result.validation_errors == []
        assert result.name_match is True
        assert result.policy_match is True
        assert result.form_matches_submission is True


# --- Decision enforcement tests ---


class TestDecisionEnforcement:
    def test_approval_blocked_by_evidence_errors(self) -> None:
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.1},
            {"validation_errors": ["Missing claimant name"]},
        )
        assert result.decision == "ESCALATE"
        assert result.approved_amount is None

    def test_approval_allowed_with_clean_evidence(self) -> None:
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.1},
            {"validation_errors": []},
        )
        assert result.decision == "APPROVE"
        assert result.approved_amount == 7900

    def test_approval_allowed_without_evidence(self) -> None:
        """No evidence_consistency passed — should not block (backward compat)."""
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(decision, {"score": 0.1}, None)
        assert result.decision == "APPROVE"

    def test_escalate_not_overridden_by_evidence(self) -> None:
        decision = AdjudicationDecision(
            decision="ESCALATE", confidence=0.5, escalation_reason="fraud"
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.5},
            {"validation_errors": ["some error"]},
        )
        assert result.decision == "ESCALATE"

    def test_approval_blocked_by_fraud_score(self) -> None:
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.5},
            {"validation_errors": []},
        )
        assert result.decision == "ESCALATE"

    def test_approval_blocked_by_low_confidence(self) -> None:
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.5, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.1},
            {"validation_errors": []},
        )
        assert result.decision == "ESCALATE"

    def test_approval_blocked_by_failed_doc_extraction(self) -> None:
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.1},
            {"validation_errors": []},
            doc_extraction={"status": "failed", "error": "Azure unavailable"},
        )
        assert result.decision == "ESCALATE"
        assert "extraction failed" in result.escalation_reason.lower()
        assert result.approved_amount is None

    def test_approval_allowed_with_successful_doc_extraction(self) -> None:
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.1},
            {"validation_errors": []},
            doc_extraction={"status": "completed"},
        )
        assert result.decision == "APPROVE"

    def test_approval_allowed_with_no_doc_extraction(self) -> None:
        """No doc_extraction passed — backward compat, should not block."""
        decision = AdjudicationDecision(
            decision="APPROVE", confidence=0.9, approved_amount=7900
        )
        result = _enforce_decision_rules(
            decision,
            {"score": 0.1},
            {"validation_errors": []},
            doc_extraction=None,
        )
        assert result.decision == "APPROVE"


class TestClaimRecordPersistsSubmittedFields:
    def test_claimant_name_persisted(self) -> None:
        record = ClaimRecord(
            claim_id="test123",
            claimant_name="Maria Thompson",
            policy_number="AT42093871",
        )
        assert record.claimant_name == "Maria Thompson"
        assert record.policy_number == "AT42093871"

    def test_default_empty_strings(self) -> None:
        record = ClaimRecord(claim_id="test123")
        assert record.claimant_name == ""
        assert record.policy_number == ""
