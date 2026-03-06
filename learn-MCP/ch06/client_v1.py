"""
client_v1.py — Direct MCP Tool Client
======================================
This client connects to our low-level Streamable HTTP MCP server and calls
tools directly, without any LLM involvement. It is the foundation you need
to understand before adding an LLM on top.

Concepts covered:
  - Opening a Streamable HTTP transport connection
  - Creating and initializing a ClientSession
  - Listing available tools
  - Calling tools with arguments and reading results
"""

import asyncio
import json

from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

# ── Server address ────────────────────────────────────────────────────────────
# This must match the host/port/path in server.py
SERVER_URL = "http://localhost:8000/mcp"


# ── Helper ────────────────────────────────────────────────────────────────────

def print_section(title: str) -> None:
    """Print a visible section header to make output easy to read."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── Core client logic ─────────────────────────────────────────────────────────

async def main() -> None:
    """
    Entry point. We open the transport and session here, then call each
    demo function in sequence.

    The two context managers work like this:

        streamable_http_client(url)
            └─ gives us (read_stream, write_stream, _)
                └─ ClientSession(read_stream, write_stream)
                    └─ gives us `session` — the object we use for everything

    We MUST call session.initialize() before any other session method.
    It performs the MCP handshake: the client sends its capabilities and
    the server responds with its own, including its name and version.
    """
    async with streamable_http_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:

            # ── 1. Handshake ──────────────────────────────────────────────
            init_result = await session.initialize()
            print_section("Server Info (from handshake)")
            print(f"  Server name   : {init_result.serverInfo.name}")
            print(f"  Server version: {init_result.serverInfo.version}")

            # ── 2. List tools ─────────────────────────────────────────────
            # session.list_tools() returns a ListToolsResult.
            # The .tools attribute is a list of types.Tool objects, each
            # with .name, .description, and .inputSchema.
            await demo_list_tools(session)

            # ── 3. Call get_customer ──────────────────────────────────────
            # We pass a plain dict of arguments matching the tool's inputSchema.
            await demo_get_customer(session, customer_id=101)
            await demo_get_customer(session, customer_id=999)  # non-existent → error

            # ── 4. Call get_orders ────────────────────────────────────────
            await demo_get_orders(session, customer_id=101)
            await demo_get_orders(session, customer_id=102)


async def demo_list_tools(session: ClientSession) -> None:
    """
    Ask the server which tools it exposes.
    This is equivalent to what the MCP Inspector shows in its Tools tab.
    """
    print_section("Available Tools")
    result = await session.list_tools()
    for tool in result.tools:
        print(f"\n  Tool      : {tool.name}")
        print(f"  Description: {tool.description}")
        # inputSchema is a plain dict (JSON Schema object)
        required = tool.inputSchema.get("required", [])
        props = tool.inputSchema.get("properties", {})
        for param, meta in props.items():
            req_marker = "*" if param in required else " "
            print(f"    [{req_marker}] {param}: {meta.get('description', '')}")


async def demo_get_customer(session: ClientSession, customer_id: int) -> None:
    """
    Call the get_customer tool.

    session.call_tool() returns a CallToolResult.
    - result.isError  → True if the server raised an error
    - result.content  → list of content blocks (TextContent, ImageContent, etc.)

    For our server every response is a single TextContent block whose .text
    is a JSON string, so we parse it for pretty printing.
    """
    print_section(f"get_customer  (customer_id={customer_id})")

    result = await session.call_tool(
        name="get_customer",
        arguments={"customer_id": customer_id},
    )

    if result.isError:
        # The server signalled an error — content[0].text holds the message
        print(f"  ERROR: {result.content[0].text}")
        return

    # Parse and pretty-print the JSON response
    data = json.loads(result.content[0].text)
    print(json.dumps(data, indent=2))


async def demo_get_orders(session: ClientSession, customer_id: int) -> None:
    """
    Call the get_orders tool.
    Same pattern as get_customer — required argument, JSON text response.
    """
    print_section(f"get_orders  (customer_id={customer_id})")

    result = await session.call_tool(
        name="get_orders",
        arguments={"customer_id": customer_id},
    )

    if result.isError:
        print(f"  ERROR: {result.content[0].text}")
        return

    data = json.loads(result.content[0].text)
    print(f"  Customer {data['customer_id']} has {data['order_count']} order(s):")
    for order in data["orders"]:
        print(f"    - [{order['id'][:8]}...] {order['description']}")


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main())
