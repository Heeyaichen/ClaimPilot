"""Claim lookup tool — reads processed claim state for Voice Live tool/MCP calls."""

from __future__ import annotations

import logging
from typing import Any

from backend.models.voice_live import ClaimLookupResult

if __import__("typing").TYPE_CHECKING:
    from backend.services.claim_state_store import ClaimStateStore

logger = logging.getLogger(__name__)

ADJUSTER_SYSTEM_INSTRUCTIONS = (
    "You are ClaimPilot's adjuster copilot. Answer questions about the processed claim "
    "using only the claim data provided by the claim_lookup tool. "
    "Be concise and factual. If the data is not available, say so clearly. "
    "Never fabricate claim details."
)


class ClaimLookupTool:
    """Reads processed claim state from ClaimStateStore for voice tool responses."""

    def __init__(self, state_store: ClaimStateStore | None = None) -> None:
        self._store = state_store

    def _get_record(self, claim_id: str) -> dict[str, Any] | None:
        """Fetch claim record and return as dict, or None."""
        if self._store is None:
            logger.warning("No state store configured for ClaimLookupTool")
            return None
        record = self._store.get_claim(claim_id)
        if record is None:
            return None
        return record.model_dump(mode="json")

    def get_claim_summary(self, claim_id: str) -> ClaimLookupResult:
        """Get a high-level summary of the claim."""
        record = self._get_record(claim_id)
        if record is None:
            return ClaimLookupResult(claim_id=claim_id, found=False, error="Claim not found")

        status = record.get("status", "UNKNOWN")
        claimant = record.get("claimant_name", "Unknown")
        policy = record.get("policy_number", "Unknown")
        decision_data = record.get("decision_result") or {}
        decision = decision_data.get("decision")
        amount = decision_data.get("approved_amount")

        summary = f"Claim {claim_id}: status={status}, claimant={claimant}, policy={policy}"
        if decision:
            summary += f", decision={decision}"
        if amount is not None:
            summary += f", amount=${amount:,.2f}"

        return ClaimLookupResult(
            claim_id=claim_id,
            found=True,
            summary=summary,
            decision=decision,
            approved_amount=amount,
        )

    def get_fraud_score(self, claim_id: str) -> ClaimLookupResult:
        """Get the fraud risk score for a claim."""
        record = self._get_record(claim_id)
        if record is None:
            return ClaimLookupResult(claim_id=claim_id, found=False, error="Claim not found")

        fraud_data = record.get("fraud_result") or {}
        score = fraud_data.get("score")
        flags = fraud_data.get("flags", [])
        recommendation = fraud_data.get("recommendation", "")

        summary = f"Fraud score: {score}"
        if flags:
            summary += f", flags: {', '.join(flags)}"
        if recommendation:
            summary += f", recommendation: {recommendation}"

        return ClaimLookupResult(
            claim_id=claim_id,
            found=True,
            summary=summary,
            fraud_score=score,
        )

    def get_damage_assessment(self, claim_id: str) -> ClaimLookupResult:
        """Get the damage assessment from image/document analysis."""
        record = self._get_record(claim_id)
        if record is None:
            return ClaimLookupResult(claim_id=claim_id, found=False, error="Claim not found")

        doc_data = record.get("doc_extraction") or {}
        image_data = record.get("image_analysis") or {}

        parts = []
        if doc_data:
            parts.append(f"Document: {doc_data.get('summary', 'extracted')}")
        if image_data:
            parts.append(f"Images: {image_data.get('summary', 'analyzed')}")

        summary = "; ".join(parts) if parts else "No damage assessment data available"

        return ClaimLookupResult(
            claim_id=claim_id,
            found=True,
            summary=summary,
            damage_assessment=summary,
        )

    def get_decision_reasoning(self, claim_id: str) -> ClaimLookupResult:
        """Get the full reasoning chain from the adjudication decision."""
        record = self._get_record(claim_id)
        if record is None:
            return ClaimLookupResult(claim_id=claim_id, found=False, error="Claim not found")

        decision_data = record.get("decision_result") or {}
        reasoning_chain = decision_data.get("reasoning_chain", [])
        decision = decision_data.get("decision")

        if not reasoning_chain:
            summary = "No reasoning chain available"
        else:
            steps = []
            for step in reasoning_chain:
                steps.append(f"{step.get('step', '?')}: {step.get('conclusion', '?')}")
            summary = " → ".join(steps)

        return ClaimLookupResult(
            claim_id=claim_id,
            found=True,
            summary=summary,
            decision=decision,
            reasoning_summary=summary,
        )

    def as_tool_definitions(self) -> list[dict[str, Any]]:
        """Return Voice Live tool definitions for claim lookup functions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_claim_summary",
                    "description": "Get a high-level summary of a processed insurance claim",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "claim_id": {
                                "type": "string",
                                "description": "The claim ID to look up",
                            },
                        },
                        "required": ["claim_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_fraud_score",
                    "description": "Get the fraud risk score and flags for a claim",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "claim_id": {
                                "type": "string",
                                "description": "The claim ID to look up",
                            },
                        },
                        "required": ["claim_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_damage_assessment",
                    "description": "Get the damage assessment from document and image analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "claim_id": {
                                "type": "string",
                                "description": "The claim ID to look up",
                            },
                        },
                        "required": ["claim_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_decision_reasoning",
                    "description": "Get the full reasoning chain from the adjudication decision",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "claim_id": {
                                "type": "string",
                                "description": "The claim ID to look up",
                            },
                        },
                        "required": ["claim_id"],
                    },
                },
            },
        ]

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> ClaimLookupResult:
        """Dispatch a tool call by name."""
        claim_id = arguments.get("claim_id", "")
        dispatch = {
            "get_claim_summary": self.get_claim_summary,
            "get_fraud_score": self.get_fraud_score,
            "get_damage_assessment": self.get_damage_assessment,
            "get_decision_reasoning": self.get_decision_reasoning,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ClaimLookupResult(
                claim_id=claim_id, found=False, error=f"Unknown tool: {tool_name}"
            )
        return handler(claim_id)
