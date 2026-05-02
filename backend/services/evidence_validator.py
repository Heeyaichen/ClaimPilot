"""Evidence consistency validator — deterministic cross-validation of claim evidence.

Validates that submitted form fields (claimant_name, policy_number) match
extracted document fields and policy index records. Unknown, mismatched, or
gibberish data triggers escalation.

Uses in-memory demo policy records when Azure Search is unavailable.
"""

from __future__ import annotations

import re

from backend.models.claim import EvidenceConsistencyResult

# Demo policy records — these correspond to demo_assets metadata
DEMO_POLICY_RECORDS: dict[str, dict[str, str]] = {
    "AT42093871": {
        "policy_holder_name": "Maria Thompson",
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_year": "2023",
        "coverage_type": "comprehensive",
        "coverage_limit": "50000",
        "deductible": "500",
        "status": "active",
    },
    "JC77120456": {
        "policy_holder_name": "James Chen",
        "vehicle_make": "Honda",
        "vehicle_model": "Accord",
        "vehicle_year": "2022",
        "coverage_type": "collision",
        "coverage_limit": "75000",
        "deductible": "1000",
        "status": "active",
    },
    "DB55309128": {
        "policy_holder_name": "Diana Brooks",
        "vehicle_make": "Ford",
        "vehicle_model": "Escape",
        "vehicle_year": "2021",
        "coverage_type": "comprehensive",
        "coverage_limit": "40000",
        "deductible": "750",
        "status": "active",
    },
}


def _normalize(name: str) -> str:
    """Normalize a name for comparison: lowercase, collapse whitespace, strip."""
    return re.sub(r"\s+", " ", name.strip()).casefold()


def _is_gibberish(value: str) -> bool:
    """Detect obviously invalid names or policy numbers.

    A string is gibberish if:
    - it's empty or only whitespace
    - it has fewer than 2 alphabetic characters (for names)
    - for policy numbers: must match ^[A-Z]{2}\\d{8}$
    """
    if not value or not value.strip():
        return True
    return False


def _is_name_gibberish(name: str) -> bool:
    """Check if a name is obviously invalid."""
    if _is_gibberish(name):
        return True
    # Must contain at least 2 alphabetic characters and a space or be >= 3 chars
    alpha_count = sum(1 for c in name if c.isalpha())
    if alpha_count < 2:
        return True
    return False


def _is_valid_policy_number(policy_number: str) -> bool:
    """Validate policy number format: ^[A-Z]{2}\\d{8}$"""
    return bool(re.match(r"^[A-Z]{2}\d{8}$", policy_number.strip()))


def _names_match(name_a: str, name_b: str) -> bool:
    """Check if two names match after normalization."""
    norm_a = _normalize(name_a)
    norm_b = _normalize(name_b)
    if not norm_a or not norm_b:
        return False
    return norm_a == norm_b


def lookup_policy(policy_number: str) -> dict[str, str] | None:
    """Look up a policy record. Uses demo records for known demo policies.

    In production, this would call SearchService.lookup_policy().
    """
    return DEMO_POLICY_RECORDS.get(policy_number.strip())


def validate_evidence(
    claimant_name_submitted: str,
    policy_number_submitted: str,
    extracted_fields: dict | None = None,
) -> EvidenceConsistencyResult:
    """Cross-validate submitted, extracted, and policy evidence.

    Rules:
    - Empty/gibberish submitted claimant name -> escalate
    - Empty/invalid submitted policy number -> escalate
    - Mismatch between submitted and extracted claimant name -> escalate
    - Mismatch between submitted and extracted policy number -> escalate
    - Policy not found in index -> escalate
    - Policy holder doesn't match submitted claimant -> escalate
    - Approval only possible when all checks pass
    """
    errors: list[str] = []
    escalation_reasons: list[str] = []
    extracted_fields = extracted_fields or {}

    result = EvidenceConsistencyResult(
        claimant_name_submitted=claimant_name_submitted,
        policy_number_submitted=policy_number_submitted,
        claimant_name_extracted=extracted_fields.get("applicant_name"),
        policy_number_extracted=extracted_fields.get("policy_number"),
    )

    # 1. Validate submitted claimant name
    if _is_gibberish(claimant_name_submitted):
        errors.append("Submitted claimant name is empty")
        escalation_reasons.append("Missing claimant name — cannot validate identity")
    elif _is_name_gibberish(claimant_name_submitted):
        errors.append(f"Submitted claimant name appears invalid: '{claimant_name_submitted}'")
        escalation_reasons.append("Claimant name appears to be gibberish")

    # 2. Validate submitted policy number
    if _is_gibberish(policy_number_submitted):
        errors.append("Submitted policy number is empty")
        escalation_reasons.append("Missing policy number — cannot validate coverage")
    elif not _is_valid_policy_number(policy_number_submitted):
        errors.append(
            f"Submitted policy number has invalid format: '{policy_number_submitted}'"
        )
        escalation_reasons.append("Policy number format is invalid")

    # 3. Check submitted vs extracted claimant name
    extracted_name = extracted_fields.get("applicant_name")
    if extracted_name and claimant_name_submitted.strip():
        if not _names_match(claimant_name_submitted, extracted_name):
            errors.append(
                f"Claimant name mismatch: submitted '{claimant_name_submitted}' "
                f"vs extracted '{extracted_name}'"
            )
            escalation_reasons.append("Submitted name does not match document")
            result.name_match = False
        else:
            result.name_match = True
    elif not extracted_name:
        # No extracted name to compare — can't validate
        pass

    # 4. Check submitted vs extracted policy number
    extracted_policy = extracted_fields.get("policy_number")
    if extracted_policy and policy_number_submitted.strip():
        if policy_number_submitted.strip() != extracted_policy.strip():
            errors.append(
                f"Policy number mismatch: submitted '{policy_number_submitted}' "
                f"vs extracted '{extracted_policy}'"
            )
            escalation_reasons.append("Submitted policy number does not match document")
            result.policy_match = False
        else:
            result.policy_match = True
    elif not extracted_policy:
        pass

    # 5. Policy lookup
    if policy_number_submitted.strip():
        policy_record = lookup_policy(policy_number_submitted)
        if policy_record:
            result.policy_lookup_status = "found"
            result.policy_holder_from_index = policy_record["policy_holder_name"]

            # 6. Policy holder name vs submitted claimant
            if claimant_name_submitted.strip():
                if not _names_match(
                    claimant_name_submitted, policy_record["policy_holder_name"]
                ):
                    errors.append(
                        f"Policy holder mismatch: submitted '{claimant_name_submitted}' "
                        f"vs policy record '{policy_record['policy_holder_name']}'"
                    )
                    escalation_reasons.append(
                        "Claimant is not the policy holder"
                    )
                else:
                    result.name_match = True
        else:
            result.policy_lookup_status = "not_found"
            errors.append(f"Policy not found in index: '{policy_number_submitted}'")
            escalation_reasons.append("Policy number not found — cannot verify coverage")

    # 7. Overall form_matches_submission
    result.form_matches_submission = (
        len(errors) == 0
        and result.policy_lookup_status == "found"
    )

    # 8. Confidence
    if not errors:
        result.confidence = 0.95
    elif len(errors) <= 1:
        result.confidence = 0.4
    else:
        result.confidence = 0.1

    result.validation_errors = errors
    result.escalation_reasons = escalation_reasons

    return result
