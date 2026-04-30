"""Unit tests for decision quality evaluation."""

from evaluation.evaluate_decision import (
    _generate_decision_samples,
    compute_decision_metrics,
    run_decision_evaluation,
)


def test_generate_decision_samples():
    samples = _generate_decision_samples(count=50, seed=42)
    assert len(samples) == 50
    assert all("decision" in s for s in samples)
    assert all("reasoning_chain" in s["decision"] for s in samples)


def test_generate_decision_samples_deterministic():
    s1 = _generate_decision_samples(count=50, seed=42)
    s2 = _generate_decision_samples(count=50, seed=42)
    assert s1 == s2


def test_decision_distribution():
    samples = _generate_decision_samples(count=200, seed=42)
    decisions = [s["decision"]["decision"] for s in samples]
    assert "APPROVE" in decisions
    assert "REJECT" in decisions
    assert "ESCALATE" in decisions


def test_compute_decision_metrics():
    samples = _generate_decision_samples(count=50, seed=42)
    metrics = compute_decision_metrics(samples)
    assert 0.0 <= metrics["groundedness"] <= 1.0
    assert metrics["sample_count"] == 50
    assert "decision_distribution" in metrics


def test_compute_decision_metrics_empty():
    metrics = compute_decision_metrics([])
    assert metrics["groundedness"] == 0.0
    assert metrics["sample_count"] == 0


def test_run_decision_evaluation():
    result = run_decision_evaluation(count=100, seed=42)
    assert "metrics" in result
    assert result["metrics"]["groundedness"] > 0.0
    assert result["metrics"]["escalation_rate"] > 0.0
