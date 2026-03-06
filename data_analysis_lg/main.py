"""
main.py — Entry point: wires MCP client + multi-agent LangGraph
================================================================
This is the glue file, same pattern as lg_mcp_01/main.py. It:
  1. Loads the API key from .env
  2. Opens the MCP session (streamable HTTP transport to port 8002)
  3. Fetches tools from the server via client.get_mcp_tools()
  4. Builds the multi-agent LangGraph via graph.build_graph()
  5. Runs a demo analysis query

Execution flow:
  main.py
    └─ graph.invoke({"messages": [HumanMessage(user_question)]})
         └─ manager     → decides first agent
         └─ data_profiler → load_csv + get_dataframe_info via MCP tools
         └─ manager     → routes to coder
         └─ coder       → execute_python (charts, stats) via MCP tools
         └─ manager     → routes to analyst
         └─ analyst     → interprets results, lists outputs
         └─ manager     → routes to reporter
         └─ reporter    → write_markdown_report via MCP tools
         └─ manager     → FINISH → END
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from langchain_core.messages import HumanMessage
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from client import get_mcp_tools
from graph import build_graph

script_dir = Path(__file__).parent
env_path = script_dir / ".env"
load_dotenv(env_path)

SERVER_URL = "http://localhost:8002/mcp"

# ── Demo analysis questions ───────────────────────────────────────────────────
# Each question triggers the full multi-agent pipeline.

DEMO_REQUESTS = [
    (
        "Correlation Analysis",
        "Calculate the corelation of the 'Ore' and 'DensityHC' columns in the 'example_data.csv' file\
            for the first 1000 rows and plot a chart of the correlation for a moving window of 50 rows.",
    ),
]


async def run_analysis(graph, label: str, user_input: str) -> None:
    """Run a single analysis request through the multi-agent graph."""
    print(f"\n{'═' * 70}")
    print(f"  USER ({label})")
    print(f"  {user_input[:120]}{'...' if len(user_input) > 120 else ''}")
    print(f"{'═' * 70}")

    final_state = await graph.ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={
            "configurable": {"thread_id": label},
            "recursion_limit": 50,
        },
    )

    # The last message in state is always the final output
    final_answer = final_state["messages"][-1].content
    print(f"\n{'─' * 70}")
    print(f"  FINAL OUTPUT:")
    print(f"{'─' * 70}")
    print(f"  {final_answer[:500]}{'...' if len(final_answer) > 500 else ''}")


async def main() -> None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found. Create .env file with your key.")
        sys.exit(1)

    print(f"Connecting to MCP server at {SERVER_URL}...")
    async with streamable_http_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"Connected to MCP server at {SERVER_URL}\n")

            # ── Fetch tools once, build graph once ────────────────────────
            langchain_tools = await get_mcp_tools(session)
            graph = build_graph(langchain_tools, api_key)

            # ── Run demo analysis ─────────────────────────────────────────
            for label, user_input in DEMO_REQUESTS:
                await run_analysis(graph, label, user_input)

    print(f"\n{'═' * 70}")
    print("  Analysis complete. Check data_analysis_lg/output/ for results.")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    asyncio.run(main())
