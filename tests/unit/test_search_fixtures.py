"""Unit tests for search fixture generation."""

from evaluation.generate_search_fixtures import (
    generate_claims_history,
    generate_policies,
)


def test_generate_policies_count():
    policies = generate_policies(count=10, seed=42)
    assert len(policies) == 10


def test_generate_policies_unique_numbers():
    policies = generate_policies(count=50, seed=42)
    numbers = [p["policy_number"] for p in policies]
    assert len(set(numbers)) == 50


def test_generate_policies_field_structure():
    policies = generate_policies(count=1, seed=42)
    p = policies[0]
    assert "policy_number" in p
    assert "policy_holder_name" in p
    assert "vehicle_make" in p
    assert "vehicle_model" in p
    assert "vehicle_year" in p
    assert "vin" in p
    assert "coverage_type" in p
    assert "coverage_limit" in p
    assert "deductible" in p
    assert "policy_start_date" in p
    assert "policy_expiry_date" in p
    assert "status" in p


def test_generate_policies_vin_length():
    policies = generate_policies(count=5, seed=42)
    for p in policies:
        assert len(p["vin"]) == 17


def test_generate_policies_expiry_after_start():
    policies = generate_policies(count=20, seed=42)
    for p in policies:
        start_year = int(p["policy_start_date"][:4])
        expiry_year = int(p["policy_expiry_date"][:4])
        assert expiry_year == start_year + 1


def test_generate_policies_deterministic():
    p1 = generate_policies(count=5, seed=42)
    p2 = generate_policies(count=5, seed=42)
    assert p1 == p2


def test_generate_claims_history_count():
    policies = generate_policies(count=5, seed=42)
    claims = generate_claims_history(policies, count=20, seed=42)
    assert len(claims) == 20


def test_generate_claims_history_linked_to_policies():
    policies = generate_policies(count=5, seed=42)
    claims = generate_claims_history(policies, count=20, seed=42)

    policy_numbers = {p["policy_number"] for p in policies}
    for c in claims:
        assert c["policy_number"] in policy_numbers


def test_generate_claims_history_field_structure():
    policies = generate_policies(count=5, seed=42)
    claims = generate_claims_history(policies, count=1, seed=42)
    c = claims[0]
    assert "claim_id" in c
    assert "policy_holder_name" in c
    assert "policy_number" in c
    assert "vin" in c
    assert "claim_type" in c
    assert "claim_date" in c
    assert "claim_amount" in c
    assert "outcome" in c
    assert "fraud_flagged" in c


def test_generate_claims_history_claim_ids_sequential():
    policies = generate_policies(count=5, seed=42)
    claims = generate_claims_history(policies, count=5, seed=42)
    ids = [c["claim_id"] for c in claims]
    assert ids == ["CLM-000001", "CLM-000002", "CLM-000003", "CLM-000004", "CLM-000005"]
