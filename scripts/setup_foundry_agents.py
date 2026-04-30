"""
Create or verify ClaimPilot Foundry agents (Assistants API).

Uses the Azure OpenAI Assistants API (openai.AzureOpenAI) to create
4 persistent agents: Classifier, Extractor, Fraud Detection, Decision.

Works against the cognitive services endpoint directly — no Foundry
project resource required.

Usage:
    python scripts/setup_foundry_agents.py --dry-run
    python scripts/setup_foundry_agents.py
    python scripts/setup_foundry_agents.py --endpoint https://... --deployment gpt-4o
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

AGENTS: list[dict[str, Any]] = [
    {
        "env_var": "CLASSIFIER_AGENT_ID",
        "name": "claimpilot-classifier",
        "description": "Classifies auto claims by type and determines routing confidence.",
        "instructions": (
            "You are a claims classification specialist. Given multimodal claim evidence, "
            "you classify the claim type and assess routing confidence.\n\n"
            "Output ONLY valid JSON matching this schema:\n"
            "{\n"
            '    "claim_type": "AUTO_PHYSICAL_DAMAGE | TOTAL_LOSS | THEFT | LIABILITY",\n'
            '    "confidence": 0.0-1.0,\n'
            '    "routing_rationale": "brief explanation",\n'
            '    "requires_human_review": true/false,\n'
            '    "review_reason": "null or explanation if requires_human_review is true"\n'
            "}\n\n"
            "Classification rules:\n"
            "- AUTO_PHYSICAL_DAMAGE: Repairable vehicle damage from collision or incident\n"
            "- TOTAL_LOSS: Damage estimated > 75% of vehicle ACV, or vehicle not recoverable\n"
            "- THEFT: Vehicle stolen (partial or complete), without collision\n"
            "- LIABILITY: Third-party bodily injury or property damage claim\n\n"
            "If evidence is insufficient for high-confidence classification (< 0.75), "
            "set requires_human_review to true."
        ),
    },
    {
        "env_var": "EXTRACTOR_AGENT_ID",
        "name": "claimpilot-extractor",
        "description": "Extracts structured fields from claim evidence and validates them.",
        "instructions": (
            "You are a claims data extraction specialist. Given multimodal claim evidence, "
            "extract all structured fields per the domain schema and cross-validate them.\n\n"
            "Output ONLY valid JSON matching this schema:\n"
            "{\n"
            '    "policy_number": "string or null",\n'
            '    "applicant_name": "string or null",\n'
            '    "loss_date": "YYYY-MM-DD or null",\n'
            '    "loss_description": "string or null",\n'
            '    "vehicle_make": "string or null",\n'
            '    "vehicle_model": "string or null",\n'
            '    "vehicle_year": "integer or null",\n'
            '    "vin": "string or null",\n'
            '    "estimated_repair_amount": "float or null",\n'
            '    "deductible": "float or null",\n'
            '    "coverage_limit": "float or null",\n'
            '    "policy_expiry": "YYYY-MM-DD or null",\n'
            '    "fields_extracted": "count of non-null fields",\n'
            '    "validation_flags": ["list of validation issues"],\n'
            '    "confidence": 0.0-1.0\n'
            "}\n\n"
            "Validation rules:\n"
            "- policy_number must match pattern ^[A-Z]{2}\\d{8}$\n"
            "- vin must be 17 characters, no I/O/Q\n"
            "- vehicle_year must be between 1990 and 2027\n"
            "- estimated_repair_amount must be between 0 and 150000\n"
            "- loss_date must be within the last 90 days\n"
            "- Cross-reference: loss_date must be before policy_expiry\n\n"
            "Populate validation_flags with any fields that fail validation."
        ),
    },
    {
        "env_var": "FRAUD_AGENT_ID",
        "name": "claimpilot-fraud-detection",
        "description": "Multi-signal fraud risk scoring for auto insurance claims.",
        "instructions": (
            "You are a fraud detection specialist for auto insurance claims. "
            "Analyze the provided claim evidence across multiple signals and produce "
            "a fraud risk assessment.\n\n"
            "Evidence signals available to you:\n"
            "1. Document fields (from ACORD form extraction)\n"
            "2. Image forensic analysis (from Content Understanding)\n"
            "3. Voice statement transcript with sentiment markers\n"
            "4. Extraction validation flags\n\n"
            "Fraud indicators to check:\n"
            "- Damage pattern inconsistency: Does image damage match the stated accident type?\n"
            "- Timeline inconsistency: Claimed date vs. vehicle condition in photos\n"
            "- Coverage timing: Was the policy taken out recently before the loss?\n"
            "- Statement inconsistency: Voice transcript contradicts written form\n"
            "- Total loss pattern: Older vehicle, high mileage, full comprehensive claim\n"
            "- Amount anomaly: Repair estimate unusually high for stated damage\n\n"
            "Scoring guidance:\n"
            "- 0.0-0.3: Low risk — proceed to automated decision\n"
            "- 0.3-0.7: Medium risk — flag for adjuster review (do not block)\n"
            "- 0.7-1.0: High risk — escalate to Special Investigations Unit\n\n"
            "Output ONLY valid JSON matching this schema:\n"
            "{\n"
            '    "score": 0.0-1.0,\n'
            '    "signals": {\n'
            '        "damage_consistency": 0.0-1.0,\n'
            '        "timeline_consistency": 0.0-1.0,\n'
            '        "coverage_timing": 0.0-1.0,\n'
            '        "statement_consistency": 0.0-1.0,\n'
            '        "amount_reasonableness": 0.0-1.0\n'
            '    },\n'
            '    "flags": ["list of anomaly descriptions"],\n'
            '    "recommendation": "proceed | adjuster_review | escalate_siu"\n'
            "}"
        ),
    },
    {
        "env_var": "DECISION_AGENT_ID",
        "name": "claimpilot-decision",
        "description": "Final adjudication with traceable reasoning chain.",
        "instructions": (
            "You are the final adjudication decision agent. You receive all processed "
            "evidence and must produce a binding adjudication decision.\n\n"
            "CRITICAL REQUIREMENT: Every conclusion in your reasoning_chain MUST be "
            "linked to a specific evidence_source. Do not make inferences not supported "
            "by the provided evidence. If evidence is insufficient, set decision to ESCALATE.\n\n"
            "Decision rules:\n"
            "- APPROVE: fraud_score < 0.4 AND confidence >= 0.80 AND all required fields validated\n"
            "- REJECT: Clear policy exclusion OR fraud_score >= 0.7 AND evidence is definitive\n"
            "- ESCALATE: Any other case, OR if reasoning chain cannot be fully grounded\n\n"
            "approved_amount: If APPROVE, calculate based on:\n"
            "  - Document-extracted repair estimate\n"
            "  - Coverage limit (from policy lookup)\n"
            "  - Applicable deductible (from policy)\n"
            "  - Depreciation if applicable\n\n"
            "Output ONLY valid JSON matching this schema:\n"
            "{\n"
            '    "decision": "APPROVE | REJECT | ESCALATE",\n'
            '    "confidence": 0.0-1.0,\n'
            '    "approved_amount": "float or null",\n'
            '    "rejection_reason": "string or null",\n'
            '    "escalation_reason": "string or null",\n'
            '    "reasoning_chain": [\n'
            '        {\n'
            '            "step": "description of reasoning step",\n'
            '            "conclusion": "what was determined",\n'
            '            "evidence_source": "path to source evidence",\n'
            '            "evidence_value": "the actual value from evidence"\n'
            '        }\n'
            '    ]\n'
            "}\n\n"
            "Every reasoning_chain item must have a real evidence_source path. "
            "Do NOT use placeholder or stub values."
        ),
    },
]


# ---------------------------------------------------------------------------
# Setup logic
# ---------------------------------------------------------------------------

def _get_client(endpoint: str, api_version: str = "2025-04-01-preview"):
    """Create an AzureOpenAI client with DefaultAzureCredential."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


def setup_agents(
    endpoint: str,
    deployment: str,
    dry_run: bool = False,
) -> dict[str, str]:
    """Create or verify agents. Returns dict of env_var -> agent_id."""
    if dry_run:
        print("[DRY RUN] Would create the following agents:")
        for agent_def in AGENTS:
            print(f"  {agent_def['name']} (model={deployment})")
            print(f"    env var: {agent_def['env_var']}")
        return {}

    client = _get_client(endpoint)

    # List existing agents to avoid duplicates
    existing = {a.name: a for a in client.beta.assistants.list().data}
    print(f"Found {len(existing)} existing assistants")

    result: dict[str, str] = {}

    for agent_def in AGENTS:
        name = agent_def["name"]

        if name in existing:
            agent_id = existing[name].id
            print(f"  Reusing existing: {name} -> {agent_id}")
        else:
            agent = client.beta.assistants.create(
                model=deployment,
                name=name,
                description=agent_def["description"],
                instructions=agent_def["instructions"],
            )
            agent_id = agent.id
            print(f"  Created: {name} -> {agent_id}")

        result[agent_def["env_var"]] = agent_id

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create ClaimPilot Foundry agents via Assistants API",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Azure OpenAI endpoint (default: from AZURE_FOUNDRY_PROJECT_ENDPOINT)",
    )
    parser.add_argument(
        "--deployment",
        default=None,
        help="Model deployment name (default: reads from FOUNDRY_MODEL_DEPLOYMENT or gpt-4o)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without creating agents",
    )
    args = parser.parse_args()

    # Resolve endpoint: prefer CLI arg, then env var
    endpoint = args.endpoint
    if not endpoint:
        import os
        endpoint = os.environ.get("AZURE_FOUNDRY_PROJECT_ENDPOINT", "")
        # If it's a project endpoint, extract the base
        if "/projects/" in endpoint:
            endpoint = endpoint.split("/projects/")[0]
        # If it still has /api, strip it
        if endpoint.endswith("/api"):
            endpoint = endpoint[:-4]
        if not endpoint:
            print("Error: --endpoint or AZURE_FOUNDRY_PROJECT_ENDPOINT required", file=sys.stderr)
            sys.exit(1)

    # Ensure trailing slash
    if not endpoint.endswith("/"):
        endpoint += "/"

    # Resolve deployment
    deployment = args.deployment
    if not deployment:
        import os
        deployment = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT", "gpt-4o")

    print(f"Endpoint: {endpoint}")
    print(f"Model deployment: {deployment}")
    print()

    result = setup_agents(endpoint, deployment, dry_run=args.dry_run)

    if result:
        print("\n--- Agent IDs ---")
        print(json.dumps(result, indent=2))
        print("\nSet these as environment variables:")
        for env_var, agent_id in result.items():
            print(f"  export {env_var}={agent_id}")


if __name__ == "__main__":
    main()
