"""Shared Foundry Agent Service client base.

Provides a common interface for all Foundry agents:
- Settings-driven project endpoint and agent IDs
- DefaultAzureCredential authentication
- Structured JSON output parsing with retry-on-malformed
- Pydantic validation of agent responses
- Fully mockable for unit testing
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Maximum retries when agent returns malformed JSON
MAX_PARSE_RETRIES = 1


class AgentResponseError(Exception):
    """Raised when an agent response cannot be parsed or validated."""


class FoundryAgentClient:
    """Base client for interacting with Foundry Agent Service.

    In production, this wraps the azure-ai-projects SDK.
    For local dev without Azure credentials, set CLAIMPILOT_USE_STUBS=1
    to fall back to deterministic stub outputs.
    """

    def __init__(
        self,
        agent_id: str | None = None,
        model_deployment: str | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = settings.azure_foundry_project_endpoint
        self._model_deployment = model_deployment or settings.foundry_model_deployment
        self._agent_id = agent_id
        self._use_stubs = settings.use_stub_agents

    def _should_use_stubs(self) -> bool:
        """Check if stub mode is explicitly enabled."""
        return self._use_stubs

    def run_agent(
        self,
        prompt: str,
        system_prompt: str,
        output_type: type[T],
        context: dict[str, Any] | None = None,
    ) -> T:
        """Run an agent and parse its structured JSON output.

        Args:
            prompt: The user message to send.
            system_prompt: The agent's system instructions.
            output_type: Pydantic model class to validate against.
            context: Optional additional context to include in the prompt.

        Returns:
            Validated instance of output_type.

        Raises:
            AgentResponseError: If the response cannot be parsed after retry.
        """
        if self._should_use_stubs():
            raise AgentResponseError(
                "Stub mode enabled — callers should handle stub path"
            )

        full_prompt = prompt
        if context:
            full_prompt += "\n\n--- Context ---\n" + json.dumps(context, default=str)

        raw_response = self._call_foundry(system_prompt, full_prompt)

        return _parse_agent_response(raw_response, output_type)

    def _call_foundry(self, system_prompt: str, user_message: str) -> str:
        """Execute the Foundry agent run via azure-ai-projects SDK.

        This method handles the actual API call. It can be overridden
        in tests or for alternative backends.
        """
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
        except ImportError as e:
            raise AgentResponseError(
                "azure-ai-projects is required for Foundry agent calls. "
                "Set CLAIMPILOT_USE_STUBS=1 for local development."
            ) from e

        credential = DefaultAzureCredential()
        client = AIProjectClient(
            endpoint=self._endpoint,
            credential=credential,
        )

        # Use pre-created agent ID if available, otherwise create ephemeral
        agent_id = self._agent_id
        ephemeral_agent = None
        if not agent_id:
            ephemeral_agent = client.agents.create_agent(
                model=self._model_deployment,
                name="claimpilot-agent",
                instructions=system_prompt,
            )
            agent_id = ephemeral_agent.id

        try:
            thread = client.agents.create_thread()
            client.agents.create_message(
                thread_id=thread.id,
                role="user",
                content=user_message,
            )
            run = client.agents.create_and_process_run(
                thread_id=thread.id,
                agent_id=agent_id,
            )

            if run.status == "failed":
                raise AgentResponseError(f"Agent run failed: {run.last_error}")

            messages = client.agents.list_messages(thread_id=thread.id)
            # Get the last assistant message
            for msg in messages.data:
                if msg.role == "assistant":
                    return msg.content[0].text if msg.content else ""

            raise AgentResponseError("No assistant response found in thread")
        finally:
            if ephemeral_agent:
                client.agents.delete_agent(ephemeral_agent.id)


def _parse_agent_response(raw: str, output_type: type[T], retries: int = 0) -> T:
    """Parse and validate an agent's JSON response.

    Handles:
    - Extracting JSON from markdown code blocks
    - Retrying once on malformed JSON
    - Pydantic validation
    """
    # Try to extract JSON from the response
    json_str = _extract_json(raw)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        if retries < MAX_PARSE_RETRIES:
            logger.warning("Malformed JSON from agent, retrying (attempt %d)", retries + 1)
            return _parse_agent_response(raw, output_type, retries + 1)
        raise AgentResponseError(f"Could not parse agent response as JSON: {raw[:200]}")

    try:
        return output_type.model_validate(data)
    except ValidationError as e:
        raise AgentResponseError(f"Agent response failed validation: {e}") from e


def _extract_json(text: str) -> str:
    """Extract JSON string from text, handling markdown code blocks."""
    # Try to find JSON in a code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON object or array
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return text.strip()
