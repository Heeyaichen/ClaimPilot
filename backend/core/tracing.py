"""Lightweight tracing for agent calls — AgentOps + Azure Application Insights.

Provides a context-manager span that records:
- agent_name, claim_id
- latency_ms, retry_count, validation_status
- errors

In production, this integrates with AgentOps and Azure Application Insights.
In local dev, traces are emitted as structured log entries.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentSpan:
    """Record of a single agent invocation."""

    agent_name: str
    claim_id: str = ""
    latency_ms: float = 0.0
    retry_count: int = 0
    validation_status: str = "pending"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "claim_id": self.claim_id,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "validation_status": self.validation_status,
            "error": self.error,
            "metadata": self.metadata,
        }


@contextmanager
def trace_agent(
    agent_name: str,
    claim_id: str = "",
    **metadata: Any,
) -> Generator[AgentSpan, None, None]:
    """Context manager that traces an agent call.

    Usage:
        with trace_agent("ClassifierAgent", claim_id="c1") as span:
            result = agent.classify(...)
            span.validation_status = "ok"

    In production, this emits to AgentOps and App Insights.
    In local dev, it logs structured trace data.
    """
    span = AgentSpan(
        agent_name=agent_name,
        claim_id=claim_id,
        metadata=metadata,
    )
    start = time.monotonic()
    try:
        yield span
        span.validation_status = span.validation_status or "ok"
    except Exception as exc:
        span.error = str(exc)
        span.validation_status = "error"
        raise
    finally:
        span.latency_ms = (time.monotonic() - start) * 1000
        _emit_trace(span)


def _emit_trace(span: AgentSpan) -> None:
    """Emit a trace span to configured backends."""
    data = span.to_dict()

    # Always log locally
    if span.error:
        logger.error("Agent trace: %s", data)
    else:
        logger.info("Agent trace: %s", data)

    # Try AgentOps if available
    try:
        import agentops  # type: ignore[import-untyped]

        agentops.record(agentops.ActionEvent(
            action_type=f"agent:{span.agent_name}",
            params=data,
            result="error" if span.error else "success",
            duration=span.latency_ms,
        ))
    except ImportError:
        pass

    # Try Azure Application Insights if available
    try:
        import importlib.util

        if importlib.util.find_spec("azure.monitor.opentelemetry"):
            logger.debug("Azure Monitor OpenTelemetry available — spans auto-collected")
    except (ImportError, ValueError):
        pass
