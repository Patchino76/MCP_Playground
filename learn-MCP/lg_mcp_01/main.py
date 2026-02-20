"""
main.py — Entry point: wires MCP client + LangGraph together
=============================================================
This is the glue file. It:
  1. Loads the API key from .env
  2. Opens the MCP session (streamable HTTP transport)
  3. Fetches tools from the server via client.get_mcp_tools()
  4. Builds the LangGraph graph via graph.build_graph()
  5. Runs a demo conversation — three different user scenarios

Execution flow for each user message:
  main.py
    └─ graph.invoke({"messages": [HumanMessage(user_input)]})
         └─ agent_node  → LLM decides which tools to call
         └─ tool_node   → StructuredTool._call() → MCP session.call_tool()
         └─ agent_node  → LLM produces final answer
         └─ END

Notice: main.py knows nothing about the loop. It just calls graph.invoke()
and gets back the final state. The graph handles all iterations internally.
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from client import get_mcp_tools
from graph import build_graph

load_dotenv()

SERVER_URL = "http://localhost:8001/mcp"

# ── Demo scenarios ─────────────────────────────────────────────────────────────
# Three realistic user reports that exercise different graph paths:
#
#   Scenario 1 — alice@company.com reports a NEW issue (screen flickering).
#                No duplicate in the ticket store → agent creates a new ticket.
#                Alice has "high" SLA → expect high priority.
#
#   Scenario 2 — bob@company.com reports a VPN issue.
#                A VPN ticket already exists (T-AA1B2C) → agent finds duplicate,
#                reports it, and skips creation.
#
#   Scenario 3 — carol@company.com reports a NEW issue (printer offline).
#                No duplicate → agent creates a ticket.
#                Carol is in IT with "critical" SLA → expect high priority.

DEMO_REQUESTS = [
    (
        "alice@company.com",
        "My laptop screen keeps flickering since yesterday's Windows update. "
        "It's making it impossible to work. My email is alice@company.com.",
    ),
    (
        "bob@company.com",
        "Hi, my VPN keeps dropping every 30 minutes or so. "
        "It's been happening since this morning. Email: bob@company.com.",
    ),
    (
        "carol@company.com",
        "The office printer on floor 3 is completely offline. "
        "Nobody in IT can print. My email is carol@company.com.",
    ),
]


async def run_scenario(graph, label: str, user_input: str) -> None:
    """Run a single user scenario through the graph and print the result."""
    print(f"\n{'═' * 65}")
    print(f"  USER ({label}): {user_input[:80]}{'...' if len(user_input) > 80 else ''}")
    print(f"{'═' * 65}")

    final_state = await graph.ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        # config lets you trace individual runs in LangSmith if you add a key later
        config={"configurable": {"thread_id": label}},
    )

    # The last message in state is always the agent's final answer
    final_answer = final_state["messages"][-1].content
    print(f"\n  ASSISTANT: {final_answer}")


async def main() -> None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found. Add it to lg_mcp_01/.env")

    async with streamable_http_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"Connected to MCP server at {SERVER_URL}\n")

            # ── Fetch tools once, build graph once ────────────────────────
            # Tools are fetched dynamically from the server — if you add a
            # new tool to tools/__init__.py and restart the server, the
            # client picks it up automatically without any code change here.
            langchain_tools = await get_mcp_tools(session)
            graph = build_graph(langchain_tools, api_key)

            # ── Run demo scenarios ─────────────────────────────────────────
            for label, user_input in DEMO_REQUESTS:
                await run_scenario(graph, label, user_input)

    print(f"\n{'═' * 65}")
    print("  Demo complete.")
    print(f"{'═' * 65}\n")


if __name__ == "__main__":
    asyncio.run(main())
