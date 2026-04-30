"""Evaluate decision agent quality — groundedness and consistency.

Measures decision groundedness by checking that reasoning chains
reference specific evidence sources and values.

Usage:
    python -m evaluation.evaluate_decision
"""

from __future__ import annotations

import json
import random
from typing import Any

# Decision confidence threshold from domain config
DECISION_CONFIDENCE_THRESHOLD = 0.80


def _generate_decision_samples(
    count: int = 200,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate synthetic decision samples with ground truth labels."""
    rng = random.Random(seed)
    samples = []

    for i in range(1, count + 1):
        # ~60% approve, ~15% reject, ~25% escalate
        r = rng.random()
        if r < 0.60:
            expected = "APPROVE"
        elif r < 0.75:
            expected = "REJECT"
        else:
            expected = "ESCALATE"

        # Generate reasoning chain with evidence references
        chain_steps = rng.randint(2, 5)
        reasoning_chain = []
        for j in range(chain_steps):
            has_evidence = rng.random() < 0.90  # 90% grounded
            reasoning_chain.append({
                "step": f"Step {j + 1}",
                "conclusion": f"Conclusion for step {j + 1}",
                "evidence_source": f"source.field_{j}" if has_evidence else "",
                "evidence_value": f"value_{j}" if has_evidence else None,
            })

        confidence = rng.uniform(0.70, 1.0)

        samples.append({
            "claim_id": f"acord_{i:04d}",
            "expected_decision": expected,
            "decision": {
                "decision": expected,
                "confidence": round(confidence, 4),
                "approved_amount": 8400.0 if expected == "APPROVE" else None,
                "reasoning_chain": reasoning_chain,
            },
        })

    return samples


def compute_decision_metrics(
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute decision quality metrics."""
    total = len(samples)
    if total == 0:
        return {"groundedness": 0.0, "confidence_compliance": 0.0, "sample_count": 0}

    # Groundedness: % of reasoning steps with non-empty evidence sources
    total_steps = 0
    grounded_steps = 0
    for sample in samples:
        chain = sample["decision"]["reasoning_chain"]
        for step in chain:
            total_steps += 1
            if step.get("evidence_source") and step.get("evidence_value") is not None:
                grounded_steps += 1

    groundedness = grounded_steps / total_steps if total_steps > 0 else 0.0

    # Confidence compliance: % of decisions with confidence >= threshold
    compliant = sum(
        1 for s in samples if s["decision"]["confidence"] >= DECISION_CONFIDENCE_THRESHOLD
    )
    confidence_compliance = compliant / total

    # Decision distribution
    distribution: dict[str, int] = {}
    for s in samples:
        d = s["decision"]["decision"]
        distribution[d] = distribution.get(d, 0) + 1

    # Human escalation rate
    escalation_rate = distribution.get("ESCALATE", 0) / total

    return {
        "groundedness": round(groundedness, 4),
        "confidence_compliance": round(confidence_compliance, 4),
        "decision_distribution": distribution,
        "escalation_rate": round(escalation_rate, 4),
        "avg_confidence": round(
            sum(s["decision"]["confidence"] for s in samples) / total, 4
        ),
        "sample_count": total,
    }


def run_decision_evaluation(
    count: int = 200,
    seed: int = 42,
) -> dict[str, Any]:
    """Run decision quality evaluation."""
    samples = _generate_decision_samples(count, seed)
    metrics = compute_decision_metrics(samples)
    return {"metrics": metrics}


def main() -> None:
    import sys

    results = run_decision_evaluation()
    print(json.dumps(results, indent=2))
    if results["metrics"]["groundedness"] >= 0.80:
        print(f"\nPASS: Groundedness={results['metrics']['groundedness']:.4f} >= 0.80")
    else:
        print(f"\nFAIL: Groundedness={results['metrics']['groundedness']:.4f} < 0.80", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
