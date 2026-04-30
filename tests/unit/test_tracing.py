"""Unit tests for agent tracing module."""

import logging

from backend.core.tracing import AgentSpan, trace_agent


def test_span_success():
    with trace_agent("ClassifierAgent", claim_id="c1") as span:
        span.validation_status = "ok"

    assert span.agent_name == "ClassifierAgent"
    assert span.claim_id == "c1"
    assert span.validation_status == "ok"
    assert span.latency_ms >= 0
    assert span.error is None


def test_span_error():
    try:
        with trace_agent("FraudAgent", claim_id="c2") as span:
            raise ValueError("test error")
    except ValueError:
        pass

    assert span.error == "test error"
    assert span.validation_status == "error"
    assert span.latency_ms > 0


def test_span_metadata():
    with trace_agent("DecisionAgent", claim_id="c3", retry_count=2) as span:
        pass

    assert span.metadata["retry_count"] == 2


def test_span_to_dict():
    span = AgentSpan(
        agent_name="Test",
        claim_id="c4",
        latency_ms=100.0,
        validation_status="ok",
    )
    d = span.to_dict()
    assert d["agent_name"] == "Test"
    assert d["claim_id"] == "c4"
    assert d["latency_ms"] == 100.0
    assert d["validation_status"] == "ok"


def test_trace_agent_emits_log(caplog):
    with caplog.at_level(logging.INFO, logger="backend.core.tracing"):
        with trace_agent("TestAgent", claim_id="c5") as span:
            span.validation_status = "ok"

    assert any("Agent trace" in r.message for r in caplog.records)
