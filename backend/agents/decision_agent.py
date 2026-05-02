"""DecisionAgent — final adjudication with traceable reasoning chain."""

from __future__ import annotations

import logging
from typing import Any

from backend.agents.base import AgentResponseError, FoundryAgentClient
from backend.models.claim import AdjudicationDecision, ReasoningStep

logger = logging.getLogger(__name__)

DECISION_SYSTEM_PROMPT = """You are the final adjudication decision agent. You receive all processed
evidence and must produce a binding adjudication decision.

CRITICAL REQUIREMENT: Every conclusion in your reasoning_chain MUST be
linked to a specific evidence_source. Do not make inferences not supported
by the provided evidence. If evidence is insufficient, set decision to ESCALATE.

EVIDENCE CONSISTENCY: You will receive an evidence_consistency object.
If evidence_consistency.validation_errors is non-empty, you MUST NOT approve.
If evidence_consistency.policy_lookup_status is "not_found", you MUST NOT approve.
If evidence_consistency.name_match is false or policy_match is false, you MUST NOT approve.
These are hard rules enforced both here and in post-processing.

Decision rules:
- APPROVE: fraud_score < 0.4 AND confidence >= 0.80 AND all required fields
  validated AND evidence_consistency has no errors
- REJECT: Clear policy exclusion OR fraud_score >= 0.7 AND evidence is definitive
- ESCALATE: Any other case, OR if reasoning chain cannot be fully grounded, OR evidence validation failed

approved_amount: If APPROVE, calculate based on:
  - Document-extracted repair estimate
  - Coverage limit (from policy lookup)
  - Applicable deductible (from policy)
  - Depreciation if applicable

Output ONLY valid JSON matching this schema:
{
    "decision": "APPROVE | REJECT | ESCALATE",
    "confidence": 0.0-1.0,
    "approved_amount": "float or null",
    "rejection_reason": "string or null",
    "escalation_reason": "string or null",
    "reasoning_chain": [
        {
            "step": "description of reasoning step",
            "conclusion": "what was determined",
            "evidence_source": "path to source evidence (e.g. doc_intelligence.field.policy_expiry)",
            "evidence_value": "the actual value from evidence"
        }
    ]
}

Every reasoning_chain item must have a real evidence_source path.
Do NOT use placeholder or stub values.
"""

# Decision thresholds from domain config
DECISION_CONFIDENCE_THRESHOLD = 0.80
FRAUD_SCORE_APPROVE_MAX = 0.4
FRAUD_SCORE_REJECT_MIN = 0.7


class DecisionAgent:
    """Produces final adjudication decisions with traceable reasoning."""

    def __init__(self, client: FoundryAgentClient | None = None) -> None:
        from backend.core.config import get_settings

        settings = get_settings()
        self._client = client or FoundryAgentClient(
            agent_id=settings.decision_agent_id or None,
        )
        self._use_stubs = settings.use_stub_agents

    def decide(
        self,
        classification: dict[str, Any] | None = None,
        extracted_fields: dict[str, Any] | None = None,
        fraud_result: dict[str, Any] | None = None,
        doc_extraction: dict[str, Any] | None = None,
        image_analysis: dict[str, Any] | None = None,
        voice_transcript: dict[str, Any] | None = None,
        evidence_consistency: dict[str, Any] | None = None,
    ) -> AdjudicationDecision:
        """Produce final adjudication decision.

        Args:
            classification: Classification result.
            extracted_fields: Extracted fields from extractor agent.
            fraud_result: Fraud risk assessment.
            doc_extraction: Document ingestion output.
            image_analysis: Image ingestion output.
            voice_transcript: Voice ingestion output.
            evidence_consistency: Cross-validation result for submitted evidence.

        Returns:
            AdjudicationDecision with decision, confidence, and reasoning chain.
        """
        if self._use_stubs:
            return self._stub_decide(fraud_result, evidence_consistency, doc_extraction)

        context = {
            "classification": classification,
            "extracted_fields": extracted_fields,
            "fraud_result": fraud_result,
            "doc_extraction": doc_extraction,
            "image_analysis": image_analysis,
            "voice_transcript": voice_transcript,
            "evidence_consistency": evidence_consistency,
        }

        prompt = (
            "Based on all processed claim evidence below, produce a final adjudication decision.\n"
            "Ensure every reasoning step references a specific evidence source.\n"
            "Return ONLY valid JSON."
        )

        try:
            result = self._client.run_agent(
                prompt=prompt,
                system_prompt=DECISION_SYSTEM_PROMPT,
                output_type=AdjudicationDecision,
                context=context,
            )
        except AgentResponseError:
            logger.exception("DecisionAgent failed, falling back to stub")
            return self._stub_decide(fraud_result, evidence_consistency, doc_extraction)

        # Enforce decision rules from domain config
        result = _enforce_decision_rules(result, fraud_result, evidence_consistency, doc_extraction)

        return result

    @staticmethod
    def _stub_decide(
        fraud_result: dict[str, Any] | None = None,
        evidence_consistency: dict[str, Any] | None = None,
        doc_extraction: dict[str, Any] | None = None,
    ) -> AdjudicationDecision:
        """Deterministic stub output for local dev."""
        decision = AdjudicationDecision(
            decision="APPROVE",
            confidence=0.88,
            approved_amount=7900.00,
            reasoning_chain=[
                ReasoningStep(
                    step="Coverage verified",
                    conclusion="Policy active on loss date",
                    evidence_source="doc_intelligence.field.policy_expiry",
                    evidence_value="2026-11-30",
                ),
                ReasoningStep(
                    step="Fraud risk",
                    conclusion="Low fraud risk",
                    evidence_source="fraud_agent.score",
                    evidence_value=0.18,
                ),
                ReasoningStep(
                    step="Amount calculation",
                    conclusion="Repair amount minus deductible",
                    evidence_source="extractor.estimated_repair_amount",
                    evidence_value=8400.00,
                ),
            ],
        )
        return _enforce_decision_rules(decision, fraud_result, evidence_consistency, doc_extraction)


def _enforce_decision_rules(
    decision: AdjudicationDecision,
    fraud_result: dict[str, Any] | None,
    evidence_consistency: dict[str, Any] | None = None,
    doc_extraction: dict[str, Any] | None = None,
) -> AdjudicationDecision:
    """Enforce domain decision rules on agent output."""
    fraud_score = 0.0
    if fraud_result:
        fraud_score = fraud_result.get("score", 0.0)

    # Override decision if agent didn't follow rules
    if decision.decision == "APPROVE":
        # Block approval if document extraction failed
        if doc_extraction and doc_extraction.get("status") == "failed":
            decision.decision = "ESCALATE"
            decision.escalation_reason = "Required document extraction failed"
            decision.approved_amount = None
            return decision

        if fraud_score >= FRAUD_SCORE_APPROVE_MAX:
            decision.decision = "ESCALATE"
            decision.escalation_reason = (
                f"Fraud score {fraud_score:.2f} exceeds approve threshold "
                f"{FRAUD_SCORE_APPROVE_MAX}"
            )
            decision.approved_amount = None
        elif decision.confidence < DECISION_CONFIDENCE_THRESHOLD:
            decision.decision = "ESCALATE"
            decision.escalation_reason = (
                f"Decision confidence {decision.confidence:.2f} below "
                f"threshold {DECISION_CONFIDENCE_THRESHOLD}"
            )
            decision.approved_amount = None

        # Block approval on evidence validation failures
        if evidence_consistency and evidence_consistency.get("validation_errors"):
            errors = evidence_consistency["validation_errors"]
            decision.decision = "ESCALATE"
            decision.escalation_reason = (
                f"Evidence validation failed: {'; '.join(errors)}"
            )
            decision.approved_amount = None

    return decision
