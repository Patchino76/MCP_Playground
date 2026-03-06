"""
graph.py — Multi-agent LangGraph for Data Analysis
====================================================
This is the heart of the project. Unlike lg_mcp_01 which has a single agent
node + tool node loop, here we build a multi-agent pipeline:

  [START] → [manager] → [data_profiler] → [manager] → [coder] → [manager]
                                                                     ↓
          [END] ← [manager] ← [reporter] ← [manager] ← [analyst] ←─┘

The Manager agent orchestrates the workflow by routing to specialist agents.
Each specialist has access to the same MCP tools but with different system
prompts guiding their behavior.

State flows through a shared MessagesState, with each agent appending its
output. The Manager reads the full conversation and decides who goes next.

Key LangGraph concepts used:
  - MessagesState     : shared message list across all nodes
  - StateGraph        : the graph builder
  - ToolNode          : pre-built node that executes tool calls
  - Conditional edges : Manager decides which specialist runs next
  - Custom state      : we extend MessagesState with a 'next_agent' field
"""

import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage,
)
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, MessagesState, END, START
from langgraph.prebuilt import ToolNode, tools_condition

GROQ_MODEL = "openai/gpt-oss-120b"

# Max characters to keep from any single tool response
MAX_TOOL_OUTPUT_CHARS = 1500


# ── Extended state ────────────────────────────────────────────────────────────
# We add 'next_agent' so the manager can signal who should run next.

class AnalysisState(MessagesState):
    next_agent: str


# ── System prompts ────────────────────────────────────────────────────────────

MANAGER_PROMPT = """You are the Manager coordinating a data analysis team. Be very brief.

Team: data_profiler, coder, analyst, reporter.

Workflow: data_profiler → coder → analyst → reporter → FINISH

Respond with a 1-2 sentence instruction, then on its own line:
NEXT: <agent_name>
or NEXT: FINISH when done.

Example response:
Please load example_data.csv and profile its structure.
NEXT: data_profiler"""

DATA_PROFILER_PROMPT = """You are the Data Profiler. Steps:
1. Call load_csv with the file path from the user's request
2. Call get_dataframe_info with include_stats='yes'
3. Write a SHORT summary (under 300 words): shape, columns, types, nulls, key stats.

Be concise. Do NOT call execute_python — just use load_csv and get_dataframe_info."""

CODER_PROMPT = """You are the Coder agent. Write Python code using execute_python.

Available in the execution environment: df (DataFrame), pd, np, sns, plt, os, OUTPUT_DIR.

Write ONE single execute_python call that creates 3-4 charts and prints key stats.
Save charts: plt.savefig(os.path.join(OUTPUT_DIR, 'name.png'), dpi=150, bbox_inches='tight')
Always plt.close() after each figure. Print a brief summary of findings.

IMPORTANT: Put ALL code in a SINGLE execute_python call. Do NOT make multiple calls."""

ANALYST_PROMPT = """You are the Analyst. Interpret the results from previous agents.

Call list_output_files to see generated charts, then write a concise analysis (under 400 words):
- Key patterns, trends, correlations
- Anomalies or notable observations
- Actionable insights

Reference specific chart filenames and numbers from the profiling/coding results."""

REPORTER_PROMPT = """You are the Reporter. Create a Markdown report using write_markdown_report.

First call list_output_files to get chart filenames. Then call write_markdown_report with:
- filename: 'analysis_report.md'
- content: A Markdown report with: Title, Dataset Overview, Key Findings (with ![title](chart.png) references), Conclusions.

Keep the report under 800 words. Use chart filenames exactly as returned by list_output_files."""


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(tools: list[BaseTool], api_key: str) -> StateGraph:
    """
    Build and compile the multi-agent LangGraph.

    Parameters
    ----------
    tools   : list of LangChain-compatible tools (from client.get_mcp_tools)
    api_key : Groq API key

    Returns
    -------
    A compiled LangGraph graph ready to invoke.

    Graph shape:
        [START] → [manager] ──→ [data_profiler|coder|analyst|reporter] ──→ [tools?] ──→ [agent_return]
                      ↑                                                                        │
                      └────────────────────────────────────────────────────────────────────────┘
                  (FINISH) → [END]
    """

    llm = ChatGroq(model=GROQ_MODEL, api_key=api_key)
    llm_with_tools = llm.bind_tools(tools)

    # ── Message compression ───────────────────────────────────────────────
    def compress_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
        """Truncate long tool outputs to keep context within token limits."""
        compressed = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if len(content) > MAX_TOOL_OUTPUT_CHARS:
                    truncated = content[:MAX_TOOL_OUTPUT_CHARS] + "\n... [truncated]"
                    compressed.append(ToolMessage(
                        content=truncated,
                        tool_call_id=msg.tool_call_id,
                        name=msg.name,
                    ))
                else:
                    compressed.append(msg)
            elif isinstance(msg, AIMessage) and msg.content and len(msg.content) > 2000:
                # Truncate very long AI responses too
                truncated_msg = AIMessage(
                    content=msg.content[:2000] + "\n... [truncated]",
                    name=getattr(msg, "name", None),
                    tool_calls=msg.tool_calls if msg.tool_calls else [],
                )
                compressed.append(truncated_msg)
            else:
                compressed.append(msg)
        return compressed

    # ── Manager node ──────────────────────────────────────────────────────
    def manager_node(state: AnalysisState) -> dict:
        print(f"\n  [manager] Reviewing conversation ({len(state['messages'])} messages)...")

        messages = [SystemMessage(content=MANAGER_PROMPT)] + compress_messages(state["messages"])
        response = llm.invoke(messages)  # Manager doesn't need tools

        content = response.content
        print(f"  [manager] Response: {content[-200:]}")

        # Parse the NEXT: directive
        next_agent = "FINISH"
        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("NEXT:"):
                next_agent = line.split("NEXT:")[1].strip()
                break

        print(f"  [manager] Routing to: {next_agent}")

        return {
            "messages": [AIMessage(content=content, name="manager")],
            "next_agent": next_agent,
        }

    # ── Specialist agent factory ──────────────────────────────────────────
    def make_specialist_node(name: str, system_prompt: str):
        """Create a specialist agent node that can use tools."""

        def specialist_node(state: AnalysisState) -> dict:
            iteration = sum(1 for m in state["messages"] if getattr(m, "name", None) == name) + 1
            print(f"\n  [{name}] iteration {iteration} — processing...")

            messages = [SystemMessage(content=system_prompt)] + compress_messages(state["messages"])
            response = llm_with_tools.invoke(messages)

            if response.tool_calls:
                names = [tc["name"] for tc in response.tool_calls]
                print(f"  [{name}] Requesting tools: {names}")
            else:
                preview = (response.content[:100] + "...") if len(response.content) > 100 else response.content
                print(f"  [{name}] Response: \"{preview}\"")

            response.name = name
            return {"messages": [response]}

        return specialist_node

    # ── Create specialist nodes ───────────────────────────────────────────
    data_profiler_node = make_specialist_node("data_profiler", DATA_PROFILER_PROMPT)
    coder_node = make_specialist_node("coder", CODER_PROMPT)
    analyst_node = make_specialist_node("analyst", ANALYST_PROMPT)
    reporter_node = make_specialist_node("reporter", REPORTER_PROMPT)

    # ── Tool node ─────────────────────────────────────────────────────────
    tool_node = ToolNode(tools)

    # ── Router functions ──────────────────────────────────────────────────
    def manager_router(state: AnalysisState) -> str:
        """Route from manager to the next specialist or END."""
        next_agent = state.get("next_agent", "FINISH")
        if next_agent in ("data_profiler", "coder", "analyst", "reporter"):
            return next_agent
        return "end"

    def specialist_router(state: AnalysisState) -> str:
        """After a specialist: go to tools if tool_calls exist, else back to manager."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "manager"

    # ── Determine which specialist just ran (for routing back after tools) ─
    def post_tool_router(state: AnalysisState) -> str:
        """After tools execute, route back to the specialist that requested them."""
        # Walk backwards to find the last AI message with a name
        for msg in reversed(state["messages"]):
            if hasattr(msg, "tool_calls") and msg.tool_calls and getattr(msg, "name", None):
                return msg.name
        return "manager"

    # ── Graph assembly ────────────────────────────────────────────────────
    graph_builder = StateGraph(AnalysisState)

    # Register all nodes
    graph_builder.add_node("manager", manager_node)
    graph_builder.add_node("data_profiler", data_profiler_node)
    graph_builder.add_node("coder", coder_node)
    graph_builder.add_node("analyst", analyst_node)
    graph_builder.add_node("reporter", reporter_node)
    graph_builder.add_node("tools", tool_node)

    # Entry point
    graph_builder.set_entry_point("manager")

    # Manager routes to specialists or END
    graph_builder.add_conditional_edges(
        "manager",
        manager_router,
        {
            "data_profiler": "data_profiler",
            "coder": "coder",
            "analyst": "analyst",
            "reporter": "reporter",
            "end": END,
        },
    )

    # Each specialist either calls tools or returns to manager
    for specialist in ["data_profiler", "coder", "analyst", "reporter"]:
        graph_builder.add_conditional_edges(
            specialist,
            specialist_router,
            {
                "tools": "tools",
                "manager": "manager",
            },
        )

    # After tools, route back to the specialist that called them
    graph_builder.add_conditional_edges(
        "tools",
        post_tool_router,
        {
            "data_profiler": "data_profiler",
            "coder": "coder",
            "analyst": "analyst",
            "reporter": "reporter",
            "manager": "manager",
        },
    )

    return graph_builder.compile()
