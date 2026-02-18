import asyncio
import sys
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp import types
from starlette.applications import Starlette
from starlette.routing import Mount
import uvicorn

from tools import tools


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize resources on startup
    print("Server starting...")
    try:
        yield {"status": "ready"}
    finally:
        # Clean up on shutdown
        print("cleanup")


server = Server("marketing-server", lifespan=server_lifespan)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tool_list = []
    for entry in tools.values():
        tool_list.append(entry["tool"])
    return tool_list


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in tools:
        raise ValueError(f"Unknown tool: {name}")
    handler = tools[name]["handler"]
    return await handler(arguments)


# Streamable HTTP transport setup
session_manager = StreamableHTTPSessionManager(server)


@asynccontextmanager
async def app_lifespan(app: Starlette):
    async with session_manager.run():
        print("Server is running on http://localhost:8000/mcp")
        yield


app = Starlette(
    routes=[
        Mount("/mcp", app=session_manager.handle_request),
    ],
    lifespan=app_lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)