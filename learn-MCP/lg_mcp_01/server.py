"""
server.py — Low-level MCP Server for the IT Support Ticket Assistant
=====================================================================
Architecture is identical to ch06/server.py. Study that first if you
haven't — this file deliberately repeats the same pattern so you can
see it is completely reusable across different domains.

What this file does:
  1. Creates a low-level mcp Server instance with a lifespan hook
  2. Registers two handlers: list_tools and call_tool
  3. Wraps the server in a StreamableHTTPSessionManager
  4. Mounts it on a Starlette app at /mcp
  5. Serves with uvicorn on port 8001 (different from ch06's 8000)

The tools themselves live in tools/ — this file only wires them up.
"""

import asyncio
import sys
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp import types
from starlette.applications import Starlette
from starlette.routing import Mount
import uvicorn

from tools import tools


# ── Lifespan ──────────────────────────────────────────────────────────────────
# Called once on startup and once on shutdown.
# Yield a dict of shared resources if your tools need them (e.g. a DB connection).
# Our tools use module-level lists in data.py, so we just yield an empty dict.

@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    print("IT Support MCP Server starting...")
    try:
        yield {}
    finally:
        print("IT Support MCP Server shutting down.")


# ── MCP Server ────────────────────────────────────────────────────────────────

server = Server("it-support-server", lifespan=server_lifespan)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Return all tools from the registry to any connecting client."""
    return [entry["tool"] for entry in tools.values()]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch an incoming tool call to the correct handler."""
    if name not in tools:
        raise ValueError(f"Unknown tool: {name}")
    handler = tools[name]["handler"]
    return await handler(arguments)


# ── Streamable HTTP transport ─────────────────────────────────────────────────
# StreamableHTTPSessionManager wraps the MCP server and handles the HTTP/SSE
# session lifecycle. Each client connection gets its own session.

session_manager = StreamableHTTPSessionManager(server)


@asynccontextmanager
async def app_lifespan(app: Starlette):
    async with session_manager.run():
        print("Server is running on http://localhost:8001/mcp")
        yield


# ── Starlette app ─────────────────────────────────────────────────────────────
# Mount the session manager's request handler at /mcp.
# The client must connect to http://localhost:8001/mcp

app = Starlette(
    routes=[
        Mount("/mcp", app=session_manager.handle_request),
    ],
    lifespan=app_lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
