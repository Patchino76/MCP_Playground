# lg_mcp_01 — IT Support Ticket Assistant
## Part 2: Information Flow, Execution Traces & Extension Ideas

> **Part 1** covers architecture, key concepts, and file-by-file breakdown.

---

## Table of Contents

5. [Information Flow — End to End](#5-information-flow--end-to-end)
6. [The Agentic Loop — ch06 vs LangGraph](#6-the-agentic-loop--ch06-vs-langgraph)
7. [Graph Execution Traces](#7-graph-execution-traces)
   - 7.1 [Scenario 1 — New ticket (Alice)](#71-scenario-1--new-ticket-alice)
   - 7.2 [Scenario 2 — Duplicate found (Bob)](#72-scenario-2--duplicate-found-bob)
   - 7.3 [Scenario 3 — New ticket, critical SLA (Carol)](#73-scenario-3--new-ticket-critical-sla-carol)
8. [The MCP ↔ LangGraph Bridge in Detail](#8-the-mcp--langgraph-bridge-in-detail)
9. [State Evolution Through a Full Run](#9-state-evolution-through-a-full-run)
10. [How to Run](#10-how-to-run)
11. [Extension Ideas](#11-extension-ideas)

---

## 5. Information Flow — End to End

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

## 6. The Agentic Loop — ch06 vs LangGraph

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

| Concern | Where it lives |
|---------|----------------|
| LLM reasoning | `agent_node` function |
| Tool execution | `ToolNode` (pre-built) |
| Loop control | `tools_condition` (pre-built) |
| State management | `MessagesState` + `add_messages` reducer |
| History accumulation | Automatic via reducer |

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

The LangGraph version has **3 lines** where ch06 has **~15 lines**. More importantly, those 3 lines are *declarative* — they describe the shape of the agent, not the mechanics of running it.

---

## 7. Graph Execution Traces

### 7.1 Scenario 1 — New ticket (Alice)

**Input:** `"My laptop screen keeps flickering... alice@company.com"`

```
Iteration 1
  agent_node receives:
    [SystemMessage, HumanMessage]
  LLM responds:
    AIMessage(tool_calls=[search_tickets(keyword="flickering")])
  tools_condition → "tools"

  tool_node executes:
    search_tickets("flickering") → MCP → {match_count: 0, tickets: []}
  ToolMessage appended to state
  edge → "agent"

Iteration 2
  agent_node receives:
    [SystemMessage, HumanMessage, AIMessage(tc1), ToolMessage(r1)]
  LLM responds:
    AIMessage(tool_calls=[get_user_profile(email="alice@company.com")])
  tools_condition → "tools"

  tool_node executes:
    get_user_profile("alice@company.com") → MCP → {sla_tier: "high", ...}
  ToolMessage appended to state
  edge → "agent"

Iteration 3
  agent_node receives:
    [SystemMessage, HumanMessage, AIMessage(tc1), ToolMessage(r1),
     AIMessage(tc2), ToolMessage(r2)]
  LLM responds:
    AIMessage(tool_calls=[create_ticket(title=..., priority="high")])
  tools_condition → "tools"

  tool_node executes:
    create_ticket(...) → MCP → {id: "T-37DFCE", status: "open", ...}
  ToolMessage appended to state
  edge → "agent"

Iteration 4
  agent_node receives: all 7 messages above
  LLM responds:
    AIMessage(content="I've filed ticket T-37DFCE (priority: High)...")
    ← no tool_calls
  tools_condition → END

Final state["messages"]: 8 messages
  [Human, AI(tc), Tool, AI(tc), Tool, AI(tc), Tool, AI(final)]
Graph iterations: 4
MCP calls: 3
```

### 7.2 Scenario 2 — Duplicate found (Bob)

**Input:** `"My VPN keeps dropping every 30 minutes... bob@company.com"`

```
Iteration 1
  agent_node receives:
    [SystemMessage, HumanMessage]
  LLM responds:
    AIMessage(tool_calls=[search_tickets(keyword="VPN")])
  tools_condition → "tools"

  tool_node executes:
    search_tickets("VPN") → MCP → {
      match_count: 1,
      tickets: [{id: "T-AA1B2C", title: "VPN disconnects every 30 minutes", ...}]
    }
  ToolMessage appended to state
  edge → "agent"

Iteration 2
  agent_node receives:
    [SystemMessage, HumanMessage, AIMessage(tc1), ToolMessage(r1)]
  LLM responds:
    AIMessage(content="There's already an open ticket T-AA1B2C for this issue...")
    ← no tool_calls — agent decided the duplicate is sufficient
  tools_condition → END

Final state["messages"]: 4 messages
  [Human, AI(tc), Tool, AI(final)]
Graph iterations: 2   ← half as many as Scenario 1
MCP calls: 1          ← no get_user_profile, no create_ticket
```

**This is the key branching behaviour.** The agent saw a duplicate and stopped. The branching logic lives entirely in the LLM's reasoning, guided by the system prompt instruction:
> *"If no duplicate ticket exists, call create_ticket..."*

The graph topology did not change — the same `tools_condition` router was used. The LLM simply chose not to emit `tool_calls` in iteration 2.

### 7.3 Scenario 3 — New ticket, critical SLA (Carol)

**Input:** `"The office printer on floor 3 is completely offline... carol@company.com"`

```
Iteration 1
  search_tickets("printer") → {match_count: 0}

Iteration 2
  get_user_profile("carol@company.com") → {sla_tier: "critical", department: "IT"}

Iteration 3
  create_ticket(priority="high") → {id: "T-3D0769"}
  Note: "critical" SLA → agent correctly assigns "high" priority

Iteration 4
  Final answer: "Ticket T-3D0769 created (priority: High)..."
  tools_condition → END

Graph iterations: 4
MCP calls: 3
```

**Comparison across scenarios:**

| Scenario | Graph iterations | MCP calls | Reason |
|----------|-----------------|-----------|--------|
| Alice (new) | 4 | 3 | Full flow: search → profile → create |
| Bob (duplicate) | 2 | 1 | Short-circuit: search found match |
| Carol (new, critical) | 4 | 3 | Full flow, critical SLA → high priority |

---

## 8. The MCP ↔ LangGraph Bridge in Detail

This is the most architecturally interesting part of the project. Two different tool interfaces need to be unified.

```
MCP world                          LangGraph world
─────────────────────────────────────────────────────────
types.Tool                    →    BaseTool (StructuredTool)
  .name (str)                 →      .name (str)
  .description (str)          →      .description (str)
  .inputSchema (JSON Schema)  →      .args_schema (Pydantic model)
  session.call_tool()         →      ._call(**kwargs) → str
```

### Step 1 — JSON Schema → Pydantic model

LangGraph's `ToolNode` validates tool arguments using the `args_schema` Pydantic model before calling the tool. MCP tools carry their schema as a plain JSON Schema dict. We convert it:

```python
def _json_schema_to_pydantic(schema: dict, model_name: str) -> Type[BaseModel]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    field_definitions = {}
    for prop_name, prop_meta in properties.items():
        json_type = prop_meta.get("type", "string")
        python_type = int if json_type == "integer" else str
        if prop_name in required:
            field_definitions[prop_name] = (python_type, ...)   # required
        else:
            field_definitions[prop_name] = (python_type, None)  # optional

    return create_model(model_name, **field_definitions)
```

For `search_tickets`, this produces the equivalent of:
```python
class search_tickets(BaseModel):
    keyword: str   # required
```

### Step 2 — Async closure over the MCP session

```python
def mcp_tool_to_langchain(tool, session):

    async def _call(**kwargs) -> str:
        result = await session.call_tool(name=tool.name, arguments=kwargs)
        if result.isError:
            return f"Error: {result.content[0].text}"
        return result.content[0].text

    return StructuredTool.from_function(
        coroutine=_call,
        name=tool.name,
        description=tool.description,
        args_schema=args_schema,
    )
```

`_call` is a **closure** — it captures `tool.name` and `session` from the enclosing scope. Each of the 3 tools gets its own `_call` function with its own captured `tool.name`. When LangGraph calls `structured_tool.invoke({"keyword": "VPN"})`, it:

1. Validates `{"keyword": "VPN"}` against the `args_schema` Pydantic model
2. Calls `_call(keyword="VPN")`
3. `_call` fires `session.call_tool(name="search_tickets", arguments={"keyword": "VPN"})`
4. The MCP server receives the HTTP POST and executes `search_tickets`
5. The result flows back as a string

**LangGraph never knows it's talking to MCP.** From LangGraph's perspective, it's just calling a `StructuredTool` that returns a string.

---

## 9. State Evolution Through a Full Run

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

## 10. How to Run

### Prerequisites

All dependencies are managed by `uv`. From the project root:

```powershell
uv sync
```

This installs: `mcp`, `starlette`, `uvicorn`, `langgraph`, `langchain-groq`, `langchain-core`, `python-dotenv`, `pydantic`.

### Step 1 — Start the MCP server

Open a terminal in `lg_mcp_01/`:

```powershell
uv run python server.py
```

Expected output:
```
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
Server is running on http://localhost:8001/mcp
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

### Step 2 — Run the agent

Open a second terminal in `lg_mcp_01/`:

```powershell
uv run python main.py
```

Expected output:
```
Connected to MCP server at http://localhost:8001/mcp

Tools loaded from MCP server:
  - search_tickets: Search open support tickets by keyword...
  - create_ticket: Create a new IT support ticket...
  - get_user_profile: Retrieve a user's profile by their email address...

═══════════════════════════════════════════════════════════════════
  USER (alice@company.com): My laptop screen keeps flickering...
═══════════════════════════════════════════════════════════════════

  ASSISTANT: I checked for existing tickets... filed ticket T-XXXXXX...

═══════════════════════════════════════════════════════════════════
  USER (bob@company.com): Hi, my VPN keeps dropping...
═══════════════════════════════════════════════════════════════════

  ASSISTANT: There's already an open ticket T-AA1B2C for this issue...

...
```

### Inspecting the MCP server directly

You can use the MCP Inspector to browse tools and call them manually:

```powershell
npx @modelcontextprotocol/inspector http://localhost:8001/mcp
```

---

## 11. Extension Ideas

The project is deliberately minimal. Here are natural next steps, ordered by complexity:

### Easy — add a new tool

Add `list_open_tickets` to `tools/tickets.py` that returns all open tickets. Then add it to `tools/__init__.py`. The server and client pick it up automatically — zero other changes needed.

### Easy — add a new user

Add a fourth user to `user_profiles` in `data.py`. Test with a new scenario in `main.py`.

### Medium — add a `resolve_ticket` tool

```python
async def resolve_ticket(arguments: dict) -> list[types.TextContent]:
    ticket_id = arguments.get("ticket_id")
    ticket = next((t for t in tickets if t.id == ticket_id), None)
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found")
    ticket.status = "resolved"
    return [types.TextContent(type="text", text=f"Ticket {ticket_id} resolved.")]
```

Now the agent can both create and close tickets in a single conversation.

### Medium — add a logging node to the graph

```python
def log_node(state: MessagesState) -> dict:
    last = state["messages"][-1]
    print(f"[LOG] Tool result: {last.content[:80]}")
    return {}   # no new messages, just a side effect

graph.add_node("logger", log_node)
graph.add_edge("tools", "logger")
graph.add_edge("logger", "agent")
# remove: graph.add_edge("tools", "agent")
```

This demonstrates how LangGraph makes it trivial to inject steps into the loop without touching existing nodes.

### Medium — add memory across scenarios

Replace `graph.ainvoke()` with a checkpointer so the agent remembers previous conversations:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)

# Each scenario uses the same thread_id to share memory
await graph.ainvoke(input, config={"configurable": {"thread_id": "alice"}})
```

### Hard — add a human-in-the-loop approval step

Use LangGraph's `interrupt_before` to pause the graph before `create_ticket` and ask a human to confirm:

```python
graph = graph_builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"],
)
```

The graph pauses, you inspect the pending tool call, then resume with `graph.invoke(None, config)`.

### Hard — replace in-memory store with a real database

Replace the `data.py` lists with SQLite queries using `aiosqlite`. The tool handlers stay identical — only the data access layer changes. This is the natural path to a production system.
