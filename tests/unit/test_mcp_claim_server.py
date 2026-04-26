"""Unit tests for MCP claim server adapter."""

import json

from backend.mcp.claim_server import MCPClaimServerAdapter
from backend.services.claim_lookup_tool import ClaimLookupTool
from tests.unit.test_claim_lookup_tool import _mock_store


def test_get_tools_list():
    adapter = MCPClaimServerAdapter(lookup_tool=ClaimLookupTool(state_store=_mock_store()))
    tools = adapter.get_tools_list()
    assert len(tools) == 4
    for tool in tools:
        assert tool["type"] == "function"
        assert "name" in tool["function"]


def test_get_inline_config():
    adapter = MCPClaimServerAdapter(lookup_tool=ClaimLookupTool(state_store=_mock_store()))
    config = adapter.get_inline_config()
    assert "tools" in config
    assert config["tool_choice"] == "auto"
    assert len(config["tools"]) == 4


def test_get_mcp_server_config():
    adapter = MCPClaimServerAdapter()
    config = adapter.get_mcp_server_config("https://mcp.example.com/claim")
    assert len(config["mcp_servers"]) == 1
    assert config["mcp_servers"][0]["url"] == "https://mcp.example.com/claim"
    assert config["mcp_servers"][0]["name"] == "claimpilot-claim-lookup"


def test_handle_tool_call():
    adapter = MCPClaimServerAdapter(lookup_tool=ClaimLookupTool(state_store=_mock_store()))
    result_str = adapter.handle_tool_call("get_fraud_score", {"claim_id": "c1"})
    result = json.loads(result_str)
    assert result["found"] is True
    assert result["fraud_score"] == 0.18


def test_handle_mcp_request_tools_list():
    adapter = MCPClaimServerAdapter(lookup_tool=ClaimLookupTool(state_store=_mock_store()))
    response = adapter.handle_mcp_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
    })
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "tools" in response["result"]
    assert len(response["result"]["tools"]) == 4


def test_handle_mcp_request_tools_call():
    adapter = MCPClaimServerAdapter(lookup_tool=ClaimLookupTool(state_store=_mock_store()))
    response = adapter.handle_mcp_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "get_claim_summary",
            "arguments": {"claim_id": "c1"},
        },
    })
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    content = response["result"]["content"]
    assert content[0]["type"] == "text"
    result = json.loads(content[0]["text"])
    assert result["found"] is True


def test_handle_mcp_request_unknown_method():
    adapter = MCPClaimServerAdapter()
    response = adapter.handle_mcp_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "unknown/method",
    })
    assert "error" in response
    assert response["error"]["code"] == -32601
