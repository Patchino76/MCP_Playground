"""
test_interactive.py — Interactive REPL for the IT Support Agent
===============================================================
Run this instead of main.py when you want to type your own messages
and see the agent respond in real time.

Usage:
    Terminal 1:  uv run python server.py
    Terminal 2:  uv run python test_interactive.py

What this demonstrates:
  - The same LangGraph graph used in main.py, but driven by user input
  - Every agent node iteration and tool call is printed as it happens
  - You can see state["messages"] grow in real time with --verbose flag
  - Type 'quit' or 'exit' to stop

Try these inputs to exercise every tool:
  "My screen is flickering. My email is alice@company.com."
      → search_tickets + get_user_profile + create_ticket

  "My VPN keeps dropping. Email: bob@company.com."
      → search_tickets → duplicate found, no creation

  "Show me all open high-priority tickets."
      → list_open_tickets

  "Mark ticket T-AA1B2C as resolved."
      → update_ticket_status + add_comment

  "Add a note to ticket T-DD3E4F: issue also affects Teams."
      → add_comment
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from langchain_core.messages import HumanMessage
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from client import get_mcp_tools
from graph import build_graph

# Load .env from the script's directory
script_dir = Path(__file__).parent
env_path = script_dir / ".env"
load_dotenv(env_path)

SERVER_URL = "http://localhost:8001/mcp"


def print_state_verbose(state: dict, iteration: int) -> None:
    """Print the full message history for learning purposes."""
    print(f"\n  {'─'*55}")
    print(f"  STATE after iteration {iteration} — {len(state['messages'])} messages total:")
    for i, msg in enumerate(state["messages"]):
        type_label = msg.type.upper().ljust(9)
        if msg.type == "ai" and hasattr(msg, "tool_calls") and msg.tool_calls:
            calls = [f"{tc['name']}({list(tc['args'].keys())})" for tc in msg.tool_calls]
            print(f"    [{i}] {type_label} tool_calls={calls}")
        elif msg.type == "tool":
            preview = msg.content[:60].replace("\n", " ")
            print(f"    [{i}] {type_label} result='{preview}...'")
        else:
            preview = (msg.content[:60] + "...") if len(msg.content) > 60 else msg.content
            print(f"    [{i}] {type_label} '{preview}'")
    print(f"  {'─'*55}")


async def chat_loop(verbose: bool) -> None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found. Copy .env.example to .env and add your key.")
        sys.exit(1)

    print(f"\nConnecting to MCP server at {SERVER_URL}...")

    async with streamable_http_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected.\n")

            langchain_tools = await get_mcp_tools(session)
            print(f"\n  {len(langchain_tools)} tools loaded:")
            for t in langchain_tools:
                print(f"    ✓ {t.name}")

            graph = build_graph(langchain_tools, api_key)

            print("\n" + "═" * 65)
            print("  IT Support Agent — Interactive Mode")
            print("  Type your message and press Enter. Type 'quit' to exit.")
            if verbose:
                print("  --verbose: full state will be printed after each run.")
            print("═" * 65)

            turn = 0
            while True:
                try:
                    user_input = input("\n  YOU: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\nExiting.")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("\nExiting.")
                    break

                turn += 1
                print(f"\n{'─' * 65}")

                final_state = await graph.ainvoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config={"configurable": {"thread_id": f"interactive-{turn}"}},
                )

                if verbose:
                    print_state_verbose(final_state, turn)

                final_answer = final_state["messages"][-1].content
                print(f"\n  ASSISTANT: {final_answer}")
                print(f"{'─' * 65}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive IT Support Agent (LangGraph + MCP)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print the full message state after each agent run",
    )
    args = parser.parse_args()
    asyncio.run(chat_loop(verbose=args.verbose))


if __name__ == "__main__":
    main()
