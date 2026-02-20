"""
client.py — MCP Client bridge for LangGraph
============================================
In ch06/client_v2.py the client owned the entire agentic loop:
  - connect to MCP
  - fetch tools
  - run while-True loop with the LLM
  - execute tool calls
  - collect final answer

Here the responsibilities are split:
  - client.py  → connect to MCP, fetch tools, execute tool calls
  - graph.py   → own the agentic loop (the LangGraph graph)

This file exposes one key function: get_mcp_tools()
It returns a list of LangChain-compatible tool wrappers that internally
call the MCP server. LangGraph's ToolNode can use these directly.

Key concept — MCPTool:
  LangGraph expects tools that follow the LangChain BaseTool interface.
  We create a lightweight wrapper class that:
    1. Holds the tool's name, description, and JSON schema
    2. On invocation, calls the real MCP server via the shared ClientSession
  This is the bridge between the MCP world and the LangGraph world.
"""

import asyncio
import json
from typing import Any, Type

from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import mcp.types as mcp_types
from pydantic import BaseModel, create_model

SERVER_URL = "http://localhost:8001/mcp"


# ── MCP → LangChain tool conversion ──────────────────────────────────────────

def _json_schema_to_pydantic(schema: dict, model_name: str) -> Type[BaseModel]:
    """
    Build a Pydantic model class from a JSON Schema dict.

    LangGraph's ToolNode needs each tool to declare its arguments as a
    Pydantic model (the tool's `args_schema`). MCP tools carry their
    schema as a plain JSON Schema dict, so we convert it here.

    We only handle the common case: object with string/integer properties.
    That covers all three tools in this project.
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    field_definitions: dict[str, Any] = {}
    for prop_name, prop_meta in properties.items():
        json_type = prop_meta.get("type", "string")
        python_type = int if json_type == "integer" else str
        if prop_name in required:
            field_definitions[prop_name] = (python_type, ...)
        else:
            field_definitions[prop_name] = (python_type, None)

    return create_model(model_name, **field_definitions)


def mcp_tool_to_langchain(tool: mcp_types.Tool, session: ClientSession) -> BaseTool:
    """
    Wrap a single MCP tool as a LangChain StructuredTool.

    StructuredTool is the standard LangChain way to create a tool from
    an async function + a Pydantic args schema. LangGraph's ToolNode
    calls these tools automatically when the LLM requests them.

    The closure captures `session` so each tool call goes to the live
    MCP server without needing to re-connect.
    """
    args_schema = _json_schema_to_pydantic(tool.inputSchema, model_name=tool.name)

    async def _call(**kwargs: Any) -> str:
        result = await session.call_tool(name=tool.name, arguments=kwargs)
        if result.isError:
            error_text = result.content[0].text if result.content else "Unknown error"
            return f"Error: {error_text}"
        return result.content[0].text

    return StructuredTool.from_function(
        coroutine=_call,
        name=tool.name,
        description=tool.description,
        args_schema=args_schema,
    )


# ── Session factory ───────────────────────────────────────────────────────────

async def get_mcp_tools(session: ClientSession) -> list[BaseTool]:
    """
    Fetch all tools from the MCP server and return them as LangChain tools.

    Called once at startup by main.py after the session is open.
    The returned list is passed directly into the LangGraph graph.
    """
    tools_result = await session.list_tools()
    langchain_tools = [mcp_tool_to_langchain(t, session) for t in tools_result.tools]

    print("Tools loaded from MCP server:")
    for t in langchain_tools:
        print(f"  - {t.name}: {t.description[:60]}...")

    return langchain_tools
