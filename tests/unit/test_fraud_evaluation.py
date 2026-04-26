"""Unit tests for fraud detection evaluation."""

from evaluation.evaluate_fraud import (
    _generate_fraud_labels,
    _mock_fraud_detection,
    compute_fraud_metrics,
    run_fraud_evaluation,
)


def test_generate_fraud_labels_count():
    labels = _generate_fraud_labels(count=50, seed=42)
    assert len(labels) == 50
    assert all("is_fraud" in label for label in labels)


def test_generate_fraud_labels_deterministic():
    l1 = _generate_fraud_labels(count=100, seed=42)
    l2 = _generate_fraud_labels(count=100, seed=42)
    assert l1 == l2


def test_generate_fraud_labels_fraud_rate():
    labels = _generate_fraud_labels(count=1000, seed=42)
    fraud_count = sum(1 for label in labels if label["is_fraud"])
    assert 100 < fraud_count < 250  # ~15%


def test_mock_fraud_detection():
    labels = _generate_fraud_labels(count=50, seed=42)
    predictions = _mock_fraud_detection(labels, seed=42)
    assert len(predictions) == 50
    assert all("score" in p for p in predictions)


def test_compute_fraud_metrics_perfect():
    gt = [
        {"claim_id": "c1", "is_fraud": True},
        {"claim_id": "c2", "is_fraud": False},
    ]
    pred = [
        {"claim_id": "c1", "score": 0.9},
        {"claim_id": "c2", "score": 0.1},
    ]
    metrics = compute_fraud_metrics(gt, pred)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["accuracy"] == 1.0


def test_compute_fraud_metrics_empty():
    metrics = compute_fraud_metrics([], [])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0


def test_run_fraud_evaluation():
    result = run_fraud_evaluation(count=100, seed=42)
    assert "metrics" in result
    assert 0.0 <= result["metrics"]["precision"] <= 1.0
    assert 0.0 <= result["metrics"]["recall"] <= 1.0
    assert result["sample_count"] == 100
