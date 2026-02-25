"""
graph.py — LangGraph agentic graph for the IT Support Ticket Assistant
=======================================================================
This file is the heart of the project. It replaces the hand-rolled
while-True loop from ch06/client_v2.py with a proper state machine.

Compare the two approaches:

  ch06/client_v2.py (manual loop):
    messages = [user_message]
    while True:
        response = llm.chat(messages, tools=groq_tools)
        if no tool_calls: return response
        execute tools → append results → loop

  graph.py (LangGraph graph):
    graph = agent_node → (tool_calls?) → tool_node → agent_node
                       → (no tool_calls?) → END

The graph manages state, routing, and history automatically.
You define WHAT the nodes do and HOW to route between them.
LangGraph handles the loop.

Key LangGraph concepts introduced here:
  - MessagesState  : built-in state type that holds a list of messages
  - StateGraph     : the graph builder
  - ToolNode       : a pre-built node that executes tool calls
  - add_messages   : a reducer that appends new messages to state
  - tools_condition: a pre-built router — goes to tools if tool_calls exist,
                     otherwise goes to END
"""

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode, tools_condition

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an IT support assistant with access to a ticket management system.

Available tools and when to use them:
  - search_tickets        : ALWAYS call this first with a relevant keyword to check for duplicates.
  - get_user_profile      : Call this to look up a user's SLA tier by email before creating a ticket.
  - create_ticket         : Create a new ticket ONLY when no duplicate exists. Priority rules:
                              critical SLA tier → high priority
                              high SLA tier     → high priority
                              standard SLA tier → medium or low priority
  - update_ticket_status  : Change a ticket's status (open → in_progress → resolved).
                            Use this when the user says their issue is fixed or needs escalation.
  - list_open_tickets     : Use this when a user asks for a summary of active tickets.
  - add_comment           : Record notes, workarounds, or investigation details on a ticket.

Decision logic:
  - If the user reports a NEW problem  → search → get profile → create ticket → summarise
  - If a duplicate is found            → report the existing ticket ID, skip creation
  - If the user says issue is resolved → update_ticket_status to "resolved" → add_comment with resolution note
  - If the user asks "what's open?"   → list_open_tickets → summarise

Always complete all necessary tool calls before giving your final answer.
Always include the ticket ID in your response."""


def build_graph(tools: list[BaseTool], api_key: str) -> StateGraph:
    """
    Build and compile the LangGraph agent graph.

    Parameters
    ----------
    tools   : list of LangChain-compatible tools (from client.get_mcp_tools)
    api_key : Groq API key

    Returns
    -------
    A compiled LangGraph graph ready to invoke with {"messages": [...]}

    Graph shape:
        [START] → [agent] ──── has tool_calls? ──→ [tools] → [agent]
                          └─── no tool_calls?  ──→ [END]
    """

    # ── LLM ───────────────────────────────────────────────────────────────────
    # bind_tools() tells the LLM about the available tools so it can
    # request them by name in its response. This is the LangChain equivalent
    # of passing `tools=groq_tools` in ch06's groq_client.chat.completions.create()
    llm = ChatGroq(model=GROQ_MODEL, api_key=api_key)
    llm_with_tools = llm.bind_tools(tools)

    # ── Agent node ────────────────────────────────────────────────────────────
    # This function IS the agent node. It receives the full current state
    # (all messages so far) and returns the LLM's next response.
    # LangGraph automatically appends the returned message to state via
    # the MessagesState reducer (add_messages).
    def agent_node(state: MessagesState) -> dict:
        iteration = sum(1 for m in state["messages"] if m.type == "ai") + 1
        print(f"\n  [agent] iteration {iteration} — sending {len(state['messages'])} messages to LLM...")

        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)

        if response.tool_calls:
            names = [tc["name"] for tc in response.tool_calls]
            print(f"  [agent] LLM requests tool call(s): {names}")
        else:
            preview = (response.content[:80] + "...") if len(response.content) > 80 else response.content
            print(f"  [agent] LLM final answer: \"{preview}\"")

        return {"messages": [response]}

    # ── Tool node ─────────────────────────────────────────────────────────────
    # ToolNode is a pre-built LangGraph node. It reads the tool_calls from
    # the last assistant message, executes each tool, and appends the results
    # as ToolMessages back into state. No manual execution loop needed.
    tool_node = ToolNode(tools)

    # ── Graph assembly ────────────────────────────────────────────────────────
    graph_builder = StateGraph(MessagesState)

    # Register the two nodes
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)

    # Entry point: always start at the agent node
    graph_builder.set_entry_point("agent")

    # Conditional edge from agent:
    #   tools_condition checks if the last message has tool_calls
    #   → if YES: route to "tools" node
    #   → if NO:  route to END
    graph_builder.add_conditional_edges("agent", tools_condition)

    # After tools execute, always go back to the agent for the next decision
    graph_builder.add_edge("tools", "agent")

    return graph_builder.compile()
