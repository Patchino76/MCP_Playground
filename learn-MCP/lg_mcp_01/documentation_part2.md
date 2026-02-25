# lg_mcp_01 — IT Support Ticket Assistant

## Part 2: Information Flow, Execution Traces, Testing & Extension

> **Part 1** covers architecture, key concepts, and file-by-file breakdown.

---

## Table of Contents

1. [Information Flow — End to End](#1-information-flow--end-to-end)
2. [The Agentic Loop — ch06 vs LangGraph](#2-the-agentic-loop--ch06-vs-langgraph)
3. [Graph Execution Traces — All 6 Scenarios](#3-graph-execution-traces--all-6-scenarios)
   - 3.1 [Scenario 1 — New ticket (Alice, high SLA)](#31-scenario-1--new-ticket-alice-high-sla)
   - 3.2 [Scenario 2 — Duplicate found (Bob, VPN)](#32-scenario-2--duplicate-found-bob-vpn)
   - 3.3 [Scenario 3 — New ticket (Carol, critical SLA)](#33-scenario-3--new-ticket-carol-critical-sla)
   - 3.4 [Scenario 4 — Resolve ticket + add comment (Bob)](#34-scenario-4--resolve-ticket--add-comment-bob)
   - 3.5 [Scenario 5 — List open tickets (IT manager)](#35-scenario-5--list-open-tickets-it-manager)
   - 3.6 [Scenario 6 — Add comment to existing ticket (Alice)](#36-scenario-6--add-comment-to-existing-ticket-alice)
   - 3.7 [Scenario comparison table](#37-scenario-comparison-table)
4. [State Evolution Through a Full Run](#4-state-evolution-through-a-full-run)
5. [How to Run and Test](#5-how-to-run-and-test)
   - 5.1 [Prerequisites](#51-prerequisites)
   - 5.2 [Run the demo (main.py)](#52-run-the-demo-mainpy)
   - 5.3 [Interactive REPL (test_interactive.py)](#53-interactive-repl-test_interactivepy)
   - 5.4 [Inspect the MCP server directly](#54-inspect-the-mcp-server-directly)
   - 5.5 [What to look for in the output](#55-what-to-look-for-in-the-output)
6. [Extension Ideas](#6-extension-ideas)

---

## 1. Information Flow — End to End

Here is the complete data flow for a single user message, from input to final answer:

```
User types: "My screen is flickering. Email: alice@company.com"
                              │
                              ▼
                    main.py
                    graph.ainvoke({"messages": [HumanMessage(...)]})
                              │
                    ┌─────────▼──────────┐
                    │    agent_node      │
                    │                   │
                    │  input:           │
                    │   SystemMessage   │
                    │   HumanMessage    │
                    │                   │
                    │  LLM decides →    │
                    │  call             │
                    │  search_tickets   │
                    │  ("flickering")   │
                    └─────────┬──────────┘
                              │
                              │ AIMessage(tool_calls=[search_tickets])
                              │ tools_condition → "tools"
                              │
                    ┌─────────▼──────────┐
                    │    tool_node       │
                    │                   │
                    │  finds            │
                    │  StructuredTool   │
                    │  "search_tickets" │
                    │                   │
                    │  calls _call()    │
                    │  → session        │
                    │    .call_tool()   │
                    └─────────┬──────────┘
                              │
                              │ HTTP POST /mcp
                              │
                    ┌─────────▼──────────────────────────┐
                    │        server.py                    │
                    │   handle_call_tool(                 │
                    │     "search_tickets",               │
                    │     {"keyword": "flickering"}       │
                    │   )                                 │
                    │                                     │
                    │   → searches tickets[] list         │
                    │   → returns TextContent             │
                    │     {match_count: 0, tickets: []}   │
                    └─────────┬──────────────────────────┘
                              │
                              │ TextContent → ToolMessage appended to state
                              │ edge: "tools" → "agent"
                              │
                    ┌─────────▼──────────┐
                    │    agent_node      │
                    │                   │
                    │  input:           │
                    │   SystemMessage   │
                    │   HumanMessage    │
                    │   AIMessage(tc1)  │
                    │   ToolMessage(r1) │
                    │                   │
                    │  LLM decides →    │
                    │  call             │
                    │  get_user_profile │
                    │  ("alice@...")    │
                    └─────────┬──────────┘
                              │
                              │  ... same MCP round-trip ...
                              │  returns {sla_tier: "high"}
                              │
                    ┌─────────▼──────────┐
                    │    agent_node      │
                    │                   │
                    │  input: all msgs  │
                    │  + profile result │
                    │                   │
                    │  LLM decides →    │
                    │  call             │
                    │  create_ticket    │
                    │  (priority="high")│
                    └─────────┬──────────┘
                              │
                              │  ... MCP creates ticket T-XXXXXX ...
                              │
                    ┌─────────▼──────────┐
                    │    agent_node      │
                    │                   │
                    │  input: all msgs  │
                    │  + ticket result  │
                    │                   │
                    │  LLM: no more     │
                    │  tool_calls →     │
                    │  final answer     │
                    └─────────┬──────────┘
                              │
                              │ tools_condition → END
                              ▼
                    final_state["messages"][-1].content
                    → "I've filed ticket T-37DFCE (priority: High)..."
```

---

## 2. The Agentic Loop — ch06 vs LangGraph

This is the most important conceptual comparison in the project.

### ch06 approach — manual loop in `client_v2.py`

```python
async def chat(session, groq_client, groq_tools, user_message):
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=groq_tools,
            tool_choice="auto",
        )
        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            return assistant_message.content       # ← exit condition

        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = await execute_tool_call(session, name, args)
            messages.append({"role": "tool", "content": result, ...})

        # loop back to top
```

**Problems with this approach at scale:**

- Loop logic is tangled with tool execution logic — hard to modify one without touching the other
- Adding a new step (e.g., log every tool call to a DB) requires modifying the loop body
- No built-in state persistence for multi-turn conversations
- No built-in support for parallel tool calls
- Hard to visualise or debug the agent's decision path

### LangGraph approach — graph topology in `graph.py`

```python
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
```

The loop is expressed as **graph topology**, not imperative code. Each concern is isolated:

| Concern              | Where it lives                           |
| -------------------- | ---------------------------------------- |
| LLM reasoning        | `agent_node` function                    |
| Tool execution       | `ToolNode` (pre-built)                   |
| Loop control         | `tools_condition` (pre-built)            |
| State management     | `MessagesState` + `add_messages` reducer |
| History accumulation | Automatic via reducer                    |

**Adding a new step** (e.g., a logging node after every tool call) means:

```python
# Before:
graph.add_edge("tools", "agent")

# After:
graph.add_node("logger", log_node)
graph.add_edge("tools", "logger")
graph.add_edge("logger", "agent")
```

The `agent_node` and `tool_node` are completely untouched.

### Side-by-side comparison

```
ch06 while-loop                    LangGraph graph
─────────────────────────────────────────────────────────────
while True:                        graph topology:
  response = llm.chat(msgs)          agent → tools_condition
  if no tool_calls:                    → "tools" or END
    return response                  tools → agent
  append assistant msg
  for each tool_call:
    execute tool
    append tool result
  # loop
```

The LangGraph version has **3 lines** where ch06 has **~15 lines**. More importantly, those 3 lines are _declarative_ — they describe the shape of the agent, not the mechanics of running it.

---

## 3. Graph Execution Traces — All 6 Scenarios

Each trace shows exactly which nodes execute, which MCP tools are called, and how `state["messages"]` grows.

### 3.1 Scenario 1 — New ticket (Alice, high SLA)

**Input:** `"My laptop screen keeps flickering... alice@company.com"`

```python
Iteration 1  [agent node]
  receives:   [SystemMessage, HumanMessage]
  LLM output: AIMessage(tool_calls=[search_tickets(keyword="flickering")])
  → tools_condition: "tools"

  [tool node] search_tickets("flickering")
  → HTTP POST /mcp → {match_count: 0, tickets: []}
  → ToolMessage appended → edge back to "agent"

Iteration 2  [agent node]
  receives:   [Human, AI(tc1), Tool(r1)]   +SystemMessage prepended
  LLM output: AIMessage(tool_calls=[get_user_profile(email="alice@company.com")])
  → tools_condition: "tools"

  [tool node] get_user_profile("alice@company.com")
  → HTTP POST /mcp → {sla_tier: "high", department: "Engineering"}
  → ToolMessage appended → edge back to "agent"

Iteration 3  [agent node]
  receives:   [Human, AI(tc1), Tool(r1), AI(tc2), Tool(r2)]
  LLM output: AIMessage(tool_calls=[create_ticket(priority="high", ...)])
  → tools_condition: "tools"

  [tool node] create_ticket(title=..., priority="high", ...)
  → HTTP POST /mcp → {id: "T-37DFCE", status: "open", created_at: ...}
  → ToolMessage appended → edge back to "agent"

Iteration 4  [agent node]
  receives:   [Human, AI(tc1), Tool(r1), AI(tc2), Tool(r2), AI(tc3), Tool(r3)]
  LLM output: AIMessage(content="I've filed ticket T-37DFCE (high priority)...")
              ← no tool_calls
  → tools_condition: END

Summary: 4 graph iterations | 3 MCP calls | 8 messages in final state
Path:    search → get_profile → create_ticket → final_answer
```

### 3.2 Scenario 2 — Duplicate found (Bob, VPN)

**Input:** `"My VPN keeps dropping every 30 minutes... bob@company.com"`

```python
Iteration 1  [agent node]
  receives:   [SystemMessage, HumanMessage]
  LLM output: AIMessage(tool_calls=[search_tickets(keyword="VPN")])
  → tools_condition: "tools"

  [tool node] search_tickets("VPN")
  → HTTP POST /mcp → {
      match_count: 1,
      tickets: [{id: "T-AA1B2C", title: "VPN disconnects every 30 minutes",
                 status: "open", priority: "high"}]
    }
  → ToolMessage appended → edge back to "agent"

Iteration 2  [agent node]
  receives:   [Human, AI(tc1), Tool(r1)]
  LLM output: AIMessage(content="There's already ticket T-AA1B2C open for this...")
              ← no tool_calls (LLM followed system prompt: skip create if duplicate)
  → tools_condition: END

Summary: 2 graph iterations | 1 MCP call | 4 messages in final state
Path:    search → duplicate found → final_answer  (short-circuit)
```

> **Key insight:** The branching logic lives in the LLM's reasoning (guided by the system prompt), NOT in the graph topology. The same `tools_condition` router runs for every scenario — it just sees no `tool_calls` in iteration 2, so it routes to `END`. The graph is identical; the LLM's decision is different.

### 3.3 Scenario 3 — New ticket (Carol, critical SLA)

**Input:** `"The office printer on floor 3 is offline... carol@company.com"`

```python
Iteration 1  search_tickets("printer") → {match_count: 0}
Iteration 2  get_user_profile("carol@company.com") → {sla_tier: "critical", dept: "IT"}
Iteration 3  create_ticket(priority="high") → {id: "T-3D0769"}
             Note: "critical" SLA maps to "high" priority per system prompt rules
Iteration 4  Final answer: "Ticket T-3D0769 created (priority: High)..."

Summary: 4 graph iterations | 3 MCP calls
Path:    search → get_profile → create_ticket → final_answer
```

### 3.4 Scenario 4 — Resolve ticket + add comment (Bob)

**Input:** `"VPN issue is fixed. Please mark T-AA1B2C resolved. Fix was a gateway restart."`

```python
Iteration 1  [agent node]
  LLM output: AIMessage(tool_calls=[
    update_ticket_status(ticket_id="T-AA1B2C", status="resolved")
  ])

  [tool node] update_ticket_status("T-AA1B2C", "resolved")
  → HTTP POST /mcp → {id: "T-AA1B2C", old_status: "open", new_status: "resolved"}
  → ToolMessage appended → edge back to "agent"

Iteration 2  [agent node]
  LLM output: AIMessage(tool_calls=[
    add_comment(ticket_id="T-AA1B2C", comment="Resolved via gateway restart")
  ])

  [tool node] add_comment("T-AA1B2C", "Resolved via gateway restart")
  → HTTP POST /mcp → {id: "T-AA1B2C", total_comments: 1, timestamp: "2026-..."}
  → ToolMessage appended → edge back to "agent"

Iteration 3  [agent node]
  LLM output: AIMessage(content="Ticket T-AA1B2C marked resolved. Comment added.")
              ← no tool_calls
  → tools_condition: END

Summary: 3 graph iterations | 2 MCP calls | 6 messages in final state
Path:    update_status → add_comment → final_answer
Tools:   update_ticket_status, add_comment  ← these were NOT available in the original 2-tool version
```

### 3.5 Scenario 5 — List open tickets (IT manager)

**Input:** `"Show me all currently open high-priority support tickets."`

```python
Iteration 1  [agent node]
  LLM output: AIMessage(tool_calls=[
    list_open_tickets(priority_filter="high")
  ])

  [tool node] list_open_tickets("high")
  → HTTP POST /mcp → {
      priority_filter: "high",
      count: 1,
      tickets: [{id: "T-3D0769", title: "Printer offline floor 3",
                 status: "open", priority: "high", user_email: "carol@company.com"}]
    }
  → ToolMessage appended → edge back to "agent"

Iteration 2  [agent node]
  LLM output: AIMessage(content="There is 1 open high-priority ticket: T-3D0769...")
              ← no tool_calls
  → tools_condition: END

Summary: 2 graph iterations | 1 MCP call | 4 messages in final state
Path:    list_open_tickets → final_answer
```

### 3.6 Scenario 6 — Add comment to existing ticket (Alice)

**Input:** `"Add a note to T-DD3E4F: issue also affects calendar sync. alice@company.com"`

```python
Iteration 1  [agent node]
  LLM output: AIMessage(tool_calls=[
    search_tickets(keyword="Outlook")   ← LLM verifies the ticket exists first
  ])

  [tool node] search_tickets("Outlook")
  → HTTP POST /mcp → {match_count: 1, tickets: [{id: "T-DD3E4F", ...}]}
  → ToolMessage appended → edge back to "agent"

Iteration 2  [agent node]
  LLM output: AIMessage(tool_calls=[
    add_comment(ticket_id="T-DD3E4F", comment="Issue also affects calendar sync")
  ])

  [tool node] add_comment("T-DD3E4F", "Issue also affects calendar sync")
  → HTTP POST /mcp → {id: "T-DD3E4F", total_comments: 1, timestamp: "2026-..."}
  → ToolMessage appended → edge back to "agent"

Iteration 3  [agent node]
  LLM output: AIMessage(content="Added note to ticket T-DD3E4F: ...")
              ← no tool_calls
  → tools_condition: END

Summary: 3 graph iterations | 2 MCP calls | 6 messages in final state
Path:    search → add_comment → final_answer
```

### 3.7 Scenario Comparison Table

| #   | Scenario                         | Graph iterations | MCP calls | Tools used                    |
| --- | -------------------------------- | :--------------: | :-------: | ----------------------------- |
| 1   | Alice — new ticket, high SLA     |        4         |     3     | search → get_profile → create |
| 2   | Bob — VPN duplicate              |        2         |     1     | search (short-circuit)        |
| 3   | Carol — new ticket, critical SLA |        4         |     3     | search → get_profile → create |
| 4   | Bob — resolve + comment          |        3         |     2     | update_status → add_comment   |
| 5   | IT manager — list open           |        2         |     1     | list_open_tickets             |
| 6   | Alice — add note                 |        3         |     2     | search → add_comment          |

Scenarios 1 and 3 exercise the **full creation path**. Scenario 2 exercises the **short-circuit path**. Scenarios 4–6 exercise the three new tools added in this iteration.

---

## 4. State Evolution Through a Full Run

Here is how `state["messages"]` grows step by step during Scenario 1 (Alice). This shows exactly what the `add_messages` reducer does on each iteration.

```
── After main.py calls graph.ainvoke() ──────────────────────────

state["messages"] = [
  HumanMessage("My laptop screen keeps flickering... alice@company.com")
]

── After agent_node iteration 1 ─────────────────────────────────

state["messages"] = [
  HumanMessage("My laptop screen keeps flickering..."),
  AIMessage(
    content="",
    tool_calls=[
      ToolCall(id="call_abc", name="search_tickets",
               args={"keyword": "flickering"})
    ]
  )
]

── After tool_node iteration 1 ──────────────────────────────────

state["messages"] = [
  HumanMessage(...),
  AIMessage(tool_calls=[search_tickets]),
  ToolMessage(
    tool_call_id="call_abc",
    content='{"keyword":"flickering","match_count":0,"tickets":[]}'
  )
]

── After agent_node iteration 2 ─────────────────────────────────

state["messages"] = [
  HumanMessage(...),
  AIMessage(tool_calls=[search_tickets]),
  ToolMessage(search result),
  AIMessage(
    content="",
    tool_calls=[
      ToolCall(id="call_def", name="get_user_profile",
               args={"email": "alice@company.com"})
    ]
  )
]

── After tool_node iteration 2 ──────────────────────────────────

state["messages"] = [
  HumanMessage(...),
  AIMessage(tool_calls=[search_tickets]),
  ToolMessage(search result),
  AIMessage(tool_calls=[get_user_profile]),
  ToolMessage(
    tool_call_id="call_def",
    content='{"email":"alice@company.com","name":"Alice Johnson",
             "department":"Engineering","machine":"Dell XPS 15",
             "sla_tier":"high"}'
  )
]

── After agent_node iteration 3 ─────────────────────────────────

state["messages"] = [
  ... (all above) ...,
  AIMessage(
    content="",
    tool_calls=[
      ToolCall(id="call_ghi", name="create_ticket",
               args={"title": "Laptop screen flickering after Windows update",
                     "description": "...",
                     "user_email": "alice@company.com",
                     "priority": "high"})
    ]
  )
]

── After tool_node iteration 3 ──────────────────────────────────

state["messages"] = [
  ... (all above) ...,
  ToolMessage(
    tool_call_id="call_ghi",
    content='{"id":"T-37DFCE","title":"Laptop screen flickering...",
             "priority":"high","status":"open",
             "created_at":"2026-02-20T15:09:00"}'
  )
]

── After agent_node iteration 4 (final) ─────────────────────────

state["messages"] = [
  HumanMessage(...),
  AIMessage(tool_calls=[search_tickets]),
  ToolMessage(search result: no match),
  AIMessage(tool_calls=[get_user_profile]),
  ToolMessage(profile: sla_tier=high),
  AIMessage(tool_calls=[create_ticket]),
  ToolMessage(ticket: T-37DFCE created),
  AIMessage(
    content="I checked for existing tickets about screen flickering and
             found none. I retrieved your profile (Engineering dept,
             high SLA tier) and created ticket T-37DFCE with high
             priority. The support team will contact you shortly."
  )
]

main.py reads: final_state["messages"][-1].content  ← the last AIMessage
```

**Key observations:**

- The `add_messages` reducer means each node only returns `{"messages": [new_message]}` — it never needs to reconstruct the full history
- The `tool_call_id` on each `ToolMessage` links it back to the specific `ToolCall` in the preceding `AIMessage` — this is how the LLM knows which result belongs to which call
- The `SystemMessage` is NOT stored in state — it is prepended fresh on every `agent_node` call

---

## 5. How to Run and Test

### 5.1 Prerequisites

Copy `.env.example` to `.env` and add your Groq API key:

```powershell
copy .env.example .env
# Then edit .env and set GROQ_API_KEY=your_key_here
```

Get a free key at https://console.groq.com

All Python dependencies are managed by `uv`:

```powershell
uv sync
```

This installs: `mcp`, `starlette`, `uvicorn`, `langgraph`, `langchain-groq`, `langchain-core`, `python-dotenv`, `pydantic`.

### 5.2 Run the demo (main.py)

**Terminal 1 — start the MCP server:**

```powershell
uv run python server.py
```

Expected:

```
INFO:     Uvicorn running on http://0.0.0.0:8001
Server is running on http://localhost:8001/mcp
```

**Terminal 2 — run all 6 scenarios:**

```powershell
uv run python main.py
```

Expected output (abbreviated):

```
Connected to MCP server at http://localhost:8001/mcp

  6 tools loaded from MCP server:
    ✓ search_tickets
    ✓ create_ticket
    ✓ update_ticket_status
    ✓ list_open_tickets
    ✓ add_comment
    ✓ get_user_profile

═════════════════════════════════════════════════════════════════
  USER (Scenario 1 — New ticket (Alice, high SLA)): My laptop...
═════════════════════════════════════════════════════════════════

  [agent] iteration 1 — sending 1 messages to LLM...
  [agent] LLM requests tool call(s): ['search_tickets']
  [agent] iteration 2 — sending 3 messages to LLM...
  [agent] LLM requests tool call(s): ['get_user_profile']
  [agent] iteration 3 — sending 5 messages to LLM...
  [agent] LLM requests tool call(s): ['create_ticket']
  [agent] iteration 4 — sending 7 messages to LLM...
  [agent] LLM final answer: "I've filed ticket T-37DFCE..."

  ASSISTANT: I've filed ticket T-37DFCE (high priority)...

═════════════════════════════════════════════════════════════════
  USER (Scenario 2 — Duplicate found (Bob, VPN)): Hi, my VPN...
═════════════════════════════════════════════════════════════════

  [agent] iteration 1 — sending 1 messages to LLM...
  [agent] LLM requests tool call(s): ['search_tickets']
  [agent] iteration 2 — sending 3 messages to LLM...
  [agent] LLM final answer: "There's already ticket T-AA1B2C..."

  ASSISTANT: There's already an open ticket T-AA1B2C...
```

Each `[agent]` line is printed by the verbose logging added to `agent_node` — you can see the ReAct loop executing in real time.

### 5.3 Interactive REPL (test_interactive.py)

For manual testing, use the interactive mode:

```powershell
uv run python test_interactive.py
```

With `--verbose` flag to see the full `MessagesState` after each turn:

```powershell
uv run python test_interactive.py --verbose
```

Sample session:

```
  IT Support Agent — Interactive Mode
  Type your message and press Enter. Type 'quit' to exit.

  YOU: Show me all open tickets

  [agent] iteration 1 — sending 1 messages to LLM...
  [agent] LLM requests tool call(s): ['list_open_tickets']
  [agent] iteration 2 — sending 3 messages to LLM...
  [agent] LLM final answer: "There are currently 2 open tickets..."

  ASSISTANT: There are currently 2 open tickets...

  YOU: Mark T-AA1B2C as resolved

  [agent] iteration 1...
  [agent] LLM requests tool call(s): ['update_ticket_status']
  ...
```

**Suggested test inputs** to exercise every tool:

| Input                                                 | Tools triggered               |
| ----------------------------------------------------- | ----------------------------- |
| `"My screen is flickering. Email: alice@company.com"` | search → get_profile → create |
| `"My VPN keeps dropping. Email: bob@company.com"`     | search → duplicate found      |
| `"Show me all open high-priority tickets"`            | list_open_tickets             |
| `"Mark ticket T-AA1B2C as resolved"`                  | update_status → add_comment   |
| `"Add a note to T-DD3E4F: issue affects Teams too"`   | add_comment                   |

### 5.4 Inspect the MCP server directly

Use the MCP Inspector to browse all 6 tools and call them manually without the agent:

```powershell
npx @modelcontextprotocol/inspector http://localhost:8001/mcp
```

This lets you verify the server is working independently of LangGraph.

### 5.5 What to look for in the output

| What you see                               | What it means                                                               |
| ------------------------------------------ | --------------------------------------------------------------------------- |
| `[agent] iteration N — sending X messages` | A new ReAct loop iteration; X grows by 2 each round (AI + Tool)             |
| `[agent] LLM requests tool call(s): [...]` | LLM decided to act — not done yet                                           |
| `[agent] LLM final answer: "..."`          | LLM produced a message with no tool_calls — `tools_condition` routes to END |
| Scenario 2 ends after 2 iterations         | Duplicate detected — short-circuit path taken                               |
| Scenario 4 ends after 3 iterations         | Two sequential tool calls (update + comment) then final answer              |

---

## 6. Extension Ideas

The project is deliberately minimal. Here are natural next steps, ordered by complexity:

### Easy — add a new user

Add a fourth user to `user_profiles` in `data.py`. Test by typing their email in `test_interactive.py`.

### Easy — add a domain-specific tool

Add a `get_ticket_by_id` tool to `tools/tickets.py` following the 3-part pattern. Add one entry to `tools/__init__.py`. Server and client pick it up automatically — zero other file changes needed.

### Medium — add a logging node to the graph

```python
def log_node(state: MessagesState) -> dict:
    last = state["messages"][-1]
    print(f"[LOG] Tool result: {last.content[:80]}")
    return {}   # no new messages — side effect only

# In build_graph():
graph.add_node("logger", log_node)
graph.add_edge("tools", "logger")   # replace: graph.add_edge("tools", "agent")
graph.add_edge("logger", "agent")
```

`agent_node` and `tool_node` are completely untouched. This demonstrates LangGraph's composability.

### Medium — add multi-turn memory with a checkpointer

Replace `graph.ainvoke()` with a `MemorySaver` checkpointer so the agent remembers previous turns:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)

# Same thread_id = shared memory across turns
config = {"configurable": {"thread_id": "alice-session"}}
await graph.ainvoke({"messages": [HumanMessage("I reported a bug yesterday")]}, config)
await graph.ainvoke({"messages": [HumanMessage("What was my ticket ID?")]}, config)
# ↑ agent remembers the previous turn's ticket ID
```

### Hard — add human-in-the-loop approval before creating tickets

Use LangGraph's `interrupt_before` to pause the graph and ask a human to confirm before any tool node runs:

```python
graph = graph_builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"],
)

# First call — graph pauses before tools node
state = await graph.ainvoke(input, config)
pending_calls = state["messages"][-1].tool_calls
print(f"Agent wants to call: {[c['name'] for c in pending_calls]}")

# Human approves — resume
await graph.ainvoke(None, config)
```

### Hard — replace in-memory store with a real database

Replace the `data.py` lists with `aiosqlite` queries. The tool handlers (in `tools/tickets.py`) stay identical — only the data access layer changes. This is the natural path to a production system.
