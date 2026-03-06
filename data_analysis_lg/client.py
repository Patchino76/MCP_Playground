"""
client.py — MCP Client bridge for LangGraph
=============================================
Same pattern as lg_mcp_01/client.py:
  - Connects to the MCP server
  - Fetches tool descriptors
  - Wraps each as a LangChain StructuredTool
  - Returns them for LangGraph's ToolNode to use

The only difference from lg_mcp_01 is the SERVER_URL (port 8002).
"""

import json
from typing import Any, Optional, Type

from langchain_core.tools import BaseTool, StructuredTool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import mcp.types as mcp_types
from pydantic import BaseModel, create_model


SERVER_URL = "http://localhost:8002/mcp"


# ── MCP → LangChain tool conversion ──────────────────────────────────────────

def _json_schema_to_pydantic(schema: dict, model_name: str) -> Type[BaseModel]:
    """
    Build a Pydantic model class from a JSON Schema dict.

    LangGraph's ToolNode needs each tool to declare its arguments as a
    Pydantic model (the tool's `args_schema`). MCP tools carry their
    schema as a plain JSON Schema dict, so we convert it here.
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
            field_definitions[prop_name] = (Optional[python_type], None)

    return create_model(model_name, **field_definitions)


def mcp_tool_to_langchain(tool: mcp_types.Tool, session: ClientSession) -> BaseTool:
    """
    Wrap a single MCP tool as a LangChain StructuredTool.

    The closure captures `session` so each tool call goes to the live
    MCP server without needing to re-connect.
    """
    args_schema = _json_schema_to_pydantic(tool.inputSchema, model_name=tool.name)

    async def _call(**kwargs: Any) -> str:
        # Filter out None values so the MCP server doesn't receive nulls
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        result = await session.call_tool(name=tool.name, arguments=clean_kwargs)
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
    The returned list is passed directly into the LangGraph graph builder.
    """
    tools_result = await session.list_tools()
    langchain_tools = [mcp_tool_to_langchain(t, session) for t in tools_result.tools]

    print("Tools loaded from MCP server:")
    for t in langchain_tools:
        print(f"  - {t.name}: {t.description[:80]}...")

    return langchain_tools
