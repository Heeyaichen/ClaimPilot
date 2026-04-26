"""MCP-compatible claim server adapter for Voice Live tool integration.

Provides a minimal MCP-compatible interface that exposes ClaimLookupTool
functions as tools consumable by Azure Voice Live's MCP integration.

The Voice Live API can connect to an MCP server to register claim lookup
tools. This adapter translates between the MCP protocol and ClaimLookupTool.

MCP Server URL contract:
    - Endpoint: configured via VOICE_LIVE_MCP_SERVER_URL
    - Protocol: JSON-RPC 2.0 over HTTP/SSE (MCP standard)
    - Tools exposed: get_claim_summary, get_fraud_score,
      get_damage_assessment, get_decision_reasoning

In preview mode (Phase 4), the full MCP server hosting is optional.
The Voice Live session can also use inline tool definitions with
server-side dispatch via ClaimLookupTool.handle_tool_call().
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.claim_lookup_tool import ClaimLookupTool

logger = logging.getLogger(__name__)


class MCPClaimServerAdapter:
    """MCP-compatible adapter that exposes claim lookup tools.

    This can operate in two modes:
    1. Inline mode: Tool definitions are sent directly in the Voice Live
       session config, and tool calls are dispatched locally via
       handle_tool_call().
    2. Server mode: A standalone MCP server endpoint that Voice Live
       connects to remotely (requires HTTP hosting).

    Phase 4 implements inline mode. Server mode is a future roadmap item.
    """

    def __init__(self, lookup_tool: ClaimLookupTool | None = None) -> None:
        self._tool = lookup_tool or ClaimLookupTool()

    def get_tools_list(self) -> list[dict[str, Any]]:
        """Return MCP-format tool list for Voice Live session config."""
        return self._tool.as_tool_definitions()

    def get_inline_config(self) -> dict[str, Any]:
        """Return the inline tools config for Voice Live session creation.

        This is used when MCP is disabled but tools are still needed.
        """
        return {
            "tools": self.get_tools_list(),
            "tool_choice": "auto",
        }

    def get_mcp_server_config(self, server_url: str) -> dict[str, Any]:
        """Return MCP server config for Voice Live session creation.

        Used when VOICE_LIVE_ENABLE_MCP=true and a server URL is configured.
        """
        return {
            "mcp_servers": [
                {
                    "type": "url",
                    "url": server_url,
                    "name": "claimpilot-claim-lookup",
                    "description": "ClaimPilot claim data lookup tools",
                },
            ],
        }

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Handle a tool call and return JSON string result.

        This is the main entry point for dispatching Voice Live tool calls
        to the appropriate ClaimLookupTool method.
        """
        result = self._tool.handle_tool_call(tool_name, arguments)
        return json.dumps(result.model_dump())

    def handle_mcp_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a JSON-RPC 2.0 MCP request.

        Supports:
        - tools/list → returns available tools
        - tools/call → dispatches to ClaimLookupTool

        Args:
            request: JSON-RPC 2.0 request with method and params.

        Returns:
            JSON-RPC 2.0 response.
        """
        request_id = request.get("id")
        method = request.get("method", "")

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": self.get_tools_list(),
                },
            }

        if method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                result_str = self.handle_tool_call(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": result_str},
                        ],
                    },
                }
            except Exception as e:
                logger.exception("MCP tool call failed: %s", tool_name)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Tool execution failed: {e}",
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }
