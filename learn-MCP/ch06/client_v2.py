"""
client_v2.py — LLM-Driven MCP Client using Groq
=================================================
This client adds an LLM (Groq) on top of the MCP session from client_v1.
Instead of us deciding which tool to call, the LLM reads the user's message,
decides which tool(s) to call, we execute them on the MCP server, and then
the LLM turns the raw results into a natural language answer.

This is the standard "agentic tool-use loop" used by real MCP clients
like Claude Desktop, Cursor, etc.

Flow for each user message:
  1. Collect all tools from the MCP server and convert them to Groq format
  2. Send user message + tool definitions to Groq
  3. If Groq returns a tool_call → execute it on the MCP server
  4. Append the tool result to the conversation
  5. Send the updated conversation back to Groq for a final answer
  6. Print the final answer

Setup:
  Create a .env file in ch06/ with:
      GROQ_API_KEY=your_key_here
  Get a free key at https://console.groq.com
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from groq import AsyncGroq
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession
import mcp.types as mcp_types

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()  # reads GROQ_API_KEY from .env

SERVER_URL = "http://localhost:8000/mcp"
GROQ_MODEL = "openai/gpt-oss-120b"  # Groq-hosted OpenAI open-weight MoE model


# ── Tool format conversion ────────────────────────────────────────────────────

def mcp_tool_to_groq(tool: mcp_types.Tool) -> dict:
    """
    Convert an MCP types.Tool into the format Groq's chat API expects.

    Groq (like OpenAI) uses this structure for tools:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": { <JSON Schema> }
            }
        }

    The MCP Tool's .inputSchema is already a valid JSON Schema dict,
    so we can pass it directly as "parameters". No transformation needed.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        },
    }


# ── Tool execution ────────────────────────────────────────────────────────────

async def execute_tool_call(session: ClientSession, tool_name: str, tool_args: dict) -> str:
    """
    Execute a single tool call on the MCP server and return the result as a
    plain string so it can be inserted back into the Groq conversation.

    Groq expects tool results as a message with role="tool".
    The content must be a string — we JSON-serialize structured data.
    """
    print(f"\n  [MCP] Calling tool '{tool_name}' with args: {tool_args}")

    result = await session.call_tool(name=tool_name, arguments=tool_args)

    if result.isError:
        # Return the error as a string so the LLM can explain it to the user
        error_text = result.content[0].text if result.content else "Unknown error"
        print(f"  [MCP] Tool error: {error_text}")
        return f"Error: {error_text}"

    # Our tools always return a single TextContent block
    content_text = result.content[0].text
    print(f"  [MCP] Tool result: {content_text[:120]}{'...' if len(content_text) > 120 else ''}")
    return content_text


# ── Agentic loop ──────────────────────────────────────────────────────────────

async def chat(session: ClientSession, groq_client: AsyncGroq, groq_tools: list[dict], user_message: str) -> str:
    """
    Run one full turn of the tool-use loop for a single user message.

    The conversation is a list of message dicts that grows as we add:
      - the user message
      - the assistant's tool_call response
      - the tool result(s)
      - the assistant's final answer

    We loop because the LLM could theoretically call multiple tools in
    sequence before producing a final text answer (multi-step reasoning).
    In practice for our server one round is usually enough.
    """
    messages = [{"role": "user", "content": user_message}]

    while True:
        # ── Ask Groq ──────────────────────────────────────────────────────
        response = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=groq_tools,
            # "auto" means: use a tool if helpful, otherwise reply directly
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        # ── Check if Groq wants to call a tool ───────────────────────────
        if not assistant_message.tool_calls:
            # No tool call → this is the final natural language answer
            return assistant_message.content

        # ── Groq requested one or more tool calls ────────────────────────
        # We must append the assistant message first (with the tool_calls),
        # then append each tool result, then loop back to ask Groq again.
        messages.append(assistant_message)  # Groq requires this in history

        for tool_call in assistant_message.tool_calls:
            name = tool_call.function.name
            # Groq sends arguments as a JSON string — we parse it to a dict
            args = json.loads(tool_call.function.arguments)

            tool_result = await execute_tool_call(session, name, args)

            # Append the tool result as a "tool" role message.
            # tool_call_id links this result back to the specific tool_call
            # so Groq knows which call produced which result.
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

        # Loop: send the updated conversation (with tool results) back to Groq


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    """
    Set up the MCP session and Groq client, then run a small demo
    conversation that exercises both tools.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found. Create a .env file with GROQ_API_KEY=your_key")

    groq_client = AsyncGroq(api_key=api_key)

    async with streamable_http_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:

            await session.initialize()
            print(f"Connected to MCP server.\n")

            # ── Fetch tools once and convert to Groq format ───────────────
            # We do this once at startup. In a real app you might refresh
            # periodically if the server's tool list can change at runtime.
            tools_result = await session.list_tools()
            groq_tools = [mcp_tool_to_groq(t) for t in tools_result.tools]

            print("Tools available to the LLM:")
            for t in groq_tools:
                print(f"  - {t['function']['name']}: {t['function']['description']}")

            # ── Demo conversation ─────────────────────────────────────────
            demo_questions = [
                "Who is customer 102?",
                "What orders does Alice Johnson have? Her customer ID is 101.",
                "Can you look up customer 103 and tell me their orders?",
            ]

            for question in demo_questions:
                print(f"\n{'─' * 60}")
                print(f"USER: {question}")
                answer = await chat(session, groq_client, groq_tools, question)
                print(f"\nASSISTANT: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
