"""Generate synthetic policy and claims-history fixtures for Azure Search.

Produces:
- evaluation/datasets/search_fixtures/policies.json (50 records)
- evaluation/datasets/search_fixtures/claims_history.json (100 records)

Records use ACORD-compatible field names and realistic values.
Deterministic with fixed seed.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]

MAKES_MODELS = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Prius"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "HR-V"],
    "Ford": ["F-150", "Explorer", "Escape", "Mustang", "Edge"],
    "Chevrolet": ["Silverado", "Equinox", "Tahoe", "Malibu", "Traverse"],
    "Nissan": ["Altima", "Rogue", "Sentra", "Pathfinder", "Frontier"],
    "Hyundai": ["Tucson", "Elantra", "Sonata", "Santa Fe", "Kona"],
    "BMW": ["3 Series", "5 Series", "X3", "X5", "X7"],
    "Mercedes-Benz": ["C-Class", "E-Class", "GLC", "GLE", "A-Class"],
}

COVERAGE_TYPES = ["COMPREHENSIVE", "COLLISION", "LIABILITY", "COMPREHENSIVE_PLUS"]
CLAIM_TYPES = ["AUTO_PHYSICAL_DAMAGE", "TOTAL_LOSS", "THEFT", "LIABILITY"]
OUTCOMES = ["APPROVED", "REJECTED", "ESCALATED", "APPROVED", "APPROVED"]

BASE_DIR = Path(__file__).resolve().parent / "datasets" / "search_fixtures"


def _vin(rng: random.Random) -> str:
    """Generate a realistic 17-char VIN (no I/O/Q)."""
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "".join(rng.choices(chars, k=17))


def _policy_number(rng: random.Random) -> str:
    """Generate policy number matching ^[A-Z]{2}\\d{8}$."""
    return "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2)) + "".join(
        rng.choices("0123456789", k=8)
    )


def _date_in_range(rng: random.Random, year_lo: int, year_hi: int) -> str:
    year = rng.randint(year_lo, year_hi)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def generate_policies(count: int = 50, seed: int = 42) -> list[dict]:
    """Generate synthetic policy records."""
    rng = random.Random(seed)
    records = []
    used_pols = set()

    for _ in range(count):
        pol = _policy_number(rng)
        while pol in used_pols:
            pol = _policy_number(rng)
        used_pols.add(pol)

        make = rng.choice(list(MAKES_MODELS.keys()))
        model = rng.choice(MAKES_MODELS[make])
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        start = _date_in_range(rng, 2023, 2025)
        expiry_year = int(start[:4]) + 1
        expiry = f"{expiry_year}{start[4:]}"
        coverage = rng.choice(COVERAGE_TYPES)

        records.append({
            "policy_number": pol,
            "policy_holder_name": f"{first} {last}",
            "vehicle_make": make,
            "vehicle_model": model,
            "vehicle_year": rng.randint(2018, 2026),
            "vin": _vin(rng),
            "coverage_type": coverage,
            "coverage_limit": rng.choice([25000, 50000, 75000, 100000, 150000]),
            "deductible": rng.choice([250, 500, 1000]),
            "policy_start_date": start,
            "policy_expiry_date": expiry,
            "status": rng.choice(["ACTIVE", "ACTIVE", "ACTIVE", "EXPIRED"]),
        })

    return records


def generate_claims_history(
    policies: list[dict],
    count: int = 100,
    seed: int = 42,
) -> list[dict]:
    """Generate synthetic prior claims linked to policy holders."""
    rng = random.Random(seed)
    records = []

    for i in range(count):
        pol = rng.choice(policies)
        claim_date = _date_in_range(rng, 2021, 2025)

        records.append({
            "claim_id": f"CLM-{i + 1:06d}",
            "policy_holder_name": pol["policy_holder_name"],
            "policy_number": pol["policy_number"],
            "vin": pol["vin"],
            "claim_type": rng.choice(CLAIM_TYPES),
            "claim_date": claim_date,
            "claim_amount": round(rng.uniform(500, 45000), 2),
            "outcome": rng.choice(OUTCOMES),
            "fraud_flagged": rng.random() < 0.08,
        })

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate search fixtures")
    parser.add_argument("--policy-count", type=int, default=50)
    parser.add_argument("--claim-count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default=str(BASE_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    policies = generate_policies(args.policy_count, args.seed)
    claims = generate_claims_history(policies, args.claim_count, args.seed)

    (output_dir / "policies.json").write_text(json.dumps(policies, indent=2))
    (output_dir / "claims_history.json").write_text(json.dumps(claims, indent=2))

    print(f"Generated {len(policies)} policies and {len(claims)} claims → {output_dir}")


if __name__ == "__main__":
    main()
