# lg_mcp_01 — IT Support Ticket Assistant

## Part 1: Architecture, Concepts & File Breakdown

> **Part 2** covers end-to-end information flow, execution traces, state evolution, and how to run and test the project.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [The Big Picture — Two Technologies, One Agent](#2-the-big-picture--two-technologies-one-agent)
3. [Technology Deep-Dive: MCP](#3-technology-deep-dive-mcp)
   - 3.1 [What Problem Does MCP Solve?](#31-what-problem-does-mcp-solve)
   - 3.2 [The Three MCP Primitives](#32-the-three-mcp-primitives)
   - 3.3 [Low-Level vs High-Level MCP Server API](#33-low-level-vs-high-level-mcp-server-api)
   - 3.4 [The Low-Level Tool Pattern (3-Part Structure)](#34-the-low-level-tool-pattern-3-part-structure)
   - 3.5 [Streamable HTTP Transport](#35-streamable-http-transport)
   - 3.6 [The MCP Session Lifecycle](#36-the-mcp-session-lifecycle)
4. [Technology Deep-Dive: LangGraph](#4-technology-deep-dive-langgraph)
   - 4.1 [What Problem Does LangGraph Solve?](#41-what-problem-does-langgraph-solve)
   - 4.2 [The Manual Loop vs the Graph](#42-the-manual-loop-vs-the-graph)
   - 4.3 [StateGraph, Nodes, and Edges](#43-stategraph-nodes-and-edges)
   - 4.4 [MessagesState and the add_messages Reducer](#44-messagesstate-and-the-add_messages-reducer)
   - 4.5 [ToolNode and tools_condition](#45-toolnode-and-tools_condition)
   - 4.6 [The ReAct Pattern](#46-the-react-pattern)
5. [The MCP ↔ LangGraph Bridge](#5-the-mcp--langgraph-bridge)
6. [Project Architecture](#6-project-architecture)
   - 6.1 [Layer Diagram](#61-layer-diagram)
   - 6.2 [File Responsibility Map](#62-file-responsibility-map)
7. [File-by-File Breakdown](#7-file-by-file-breakdown)
   - 7.1 [schema.py](#71-schemapy)
   - 7.2 [data.py](#72-datapy)
   - 7.3 [tools/tickets.py](#73-toolsticketspy)
   - 7.4 [tools/users.py](#74-toolsuserspy)
   - 7.5 [tools/**init**.py — The Registry](#75-tools__init__py--the-registry)
   - 7.6 [server.py](#76-serverpy)
   - 7.7 [client.py](#77-clientpy)
   - 7.8 [graph.py](#78-graphpy)
   - 7.9 [main.py](#79-mainpy)

---

## 1. What This Project Is

This project is a **complete, working agentic system** built for learning. It combines two modern AI infrastructure technologies to build an IT Support Ticket Assistant:

- **MCP (Model Context Protocol)** — a standard HTTP protocol for exposing tools to AI agents
- **LangGraph** — a framework for building stateful, multi-step AI agents as directed graphs

A user types a problem in plain English. The agent autonomously:

1. Searches for duplicate tickets
2. Looks up the user's SLA tier
3. Creates a new ticket with the correct priority — or reports the duplicate
4. Can update ticket status, list open tickets, and add timestamped comments
5. Returns a natural language summary

Every design decision is fully visible. There is no magic, no hidden abstraction. Read the code top-to-bottom and you will understand exactly how a production AI agent works.

---

## 2. The Big Picture — Two Technologies, One Agent

```
┌──────────────────────────────────────────────────────────────────────┐
│                        WHAT THE USER SEES                            │
│                                                                      │
│  Input:  "My screen is flickering. Email: alice@company.com"         │
│  Output: "Ticket T-3A7F2B created (high priority)."                  │
└──────────────────────────────────────────────────────────────────────┘
                               ↕
┌──────────────────────────────────────────────────────────────────────┐
│               LANGGRAPH  (the "brain" / orchestrator)                │
│                                                                      │
│  Manages the agentic loop: decides WHEN to call tools, in what       │
│  order, accumulates full conversation history, knows when done.      │
│                                                                      │
│  graph: [START]→[agent]──tool calls?──→[tools]→[agent]→[END]        │
└──────────────────────────────────────────────────────────────────────┘
                               ↕  (client.py bridges the two worlds)
┌──────────────────────────────────────────────────────────────────────┐
│               MCP  (the "hands" / tool protocol)                     │
│                                                                      │
│  Defines HOW tools are described, discovered, and called over HTTP.  │
│  The agent asks "what tools exist?" and "run tool X with args Y".    │
│                                                                      │
│  Tools: search_tickets | create_ticket | update_ticket_status        │
│         list_open_tickets | add_comment | get_user_profile           │
└──────────────────────────────────────────────────────────────────────┘
```

**Key insight:** LangGraph and MCP are independent. LangGraph doesn't know it's talking to MCP — it just sees LangChain tools. MCP doesn't know it's called by LangGraph — it just receives HTTP requests. `client.py` is the thin bridge that connects them.

---

## 3. Technology Deep-Dive: MCP

### 3.1 What Problem Does MCP Solve?

Before MCP, every AI application needed custom integration code for each external tool. MCP is the **USB-C of AI tools** — one standard protocol that any client can use to talk to any server:

```
Without MCP:                          With MCP:

Agent ──custom code──► DB             Agent ──MCP──► DB server
Agent ──custom code──► Calendar       Agent ──MCP──► Calendar server
Agent ──custom code──► Tickets        Agent ──MCP──► Ticket server

3 different integrations              1 standard, 3 servers
```

Any MCP client (Claude Desktop, a LangGraph agent, a custom script) works with any MCP server without changes.

### 3.2 The Three MCP Primitives

| Primitive        | What it is                              | In this project                             |
| ---------------- | --------------------------------------- | ------------------------------------------- |
| **Tool**         | Named function + JSON Schema for inputs | 6 tools in `tools/`                         |
| **`list_tools`** | Client asks: "what tools do you have?"  | Called once at startup in `get_mcp_tools()` |
| **`call_tool`**  | Client says: "run tool X with args Y"   | Called per tool invocation by `ToolNode`    |

The return type for every tool call is `list[TextContent]` — a wrapper around a string (always JSON in this project).

### 3.3 Low-Level vs High-Level MCP Server API

| API                    | Code style                                   | What's hidden                          | Use when             |
| ---------------------- | -------------------------------------------- | -------------------------------------- | -------------------- |
| `FastMCP` (high-level) | `@mcp.tool()` decorator                      | Schema generation, dispatch, transport | Quick prototyping    |
| `Server` (low-level)   | Explicit `list_tools` + `call_tool` handlers | Nothing                                | Learning, production |

This project uses **low-level** deliberately so every step is visible:

```python
# HIGH-LEVEL (FastMCP) — one decorator, everything hidden:
@mcp.tool()
def search(keyword: str) -> str:
    return "results"

# LOW-LEVEL (Server) — explicit handlers, nothing hidden:
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [entry["tool"] for entry in tools.values()]   # you build the list

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    return await tools[name]["handler"](arguments)       # you dispatch manually
```

### 3.4 The Low-Level Tool Pattern (3-Part Structure)

Every tool in this project follows the **same three-part structure** — the core pattern of the low-level MCP API:

```
PART 1 — JSON Schema dict  (describes inputs to the LLM and to client.py)
──────────────────────────────────────────────────────────────────────
search_tickets_input_schema = {
  "type": "object",
  "properties": {
    "keyword": {
      "type": "string",
      "description": "Word to search in ticket titles and descriptions"
    }
  },
  "required": ["keyword"]
}
  → returned verbatim by list_tools so the LLM knows the contract
  → used by client.py to build the Pydantic validation model


PART 2 — types.Tool  (the MCP descriptor — what the client receives)
──────────────────────────────────────────────────────────────────────
search_tickets_tool = types.Tool(
  name="search_tickets",
  description="Search tickets by keyword. Always call first to check for duplicates.",
  inputSchema=search_tickets_input_schema,
)
  → returned by handle_list_tools()
  → converted to a LangChain StructuredTool by client.py
  → passed to llm.bind_tools() so the LLM can request it by name


PART 3 — async handler function  (the actual implementation)
──────────────────────────────────────────────────────────────────────
async def search_tickets(arguments: dict) -> list[types.TextContent]:
    keyword = arguments.get("keyword", "").lower()
    matches = [t for t in tickets
               if keyword in t.title.lower() or keyword in t.description.lower()]
    return [types.TextContent(type="text", text=json.dumps({"matches": ...}))]
  → called by handle_call_tool() when the LLM requests this tool
  → receives raw dict (validated upstream by Pydantic in client.py)
  → always returns a list[TextContent], even for single results
```

### 3.5 Streamable HTTP Transport

MCP supports multiple transports (stdio, SSE, Streamable HTTP). This project uses **Streamable HTTP** — the current production standard (MCP spec 2025-03-26).

```
CLIENT (main.py / client.py)              SERVER (server.py)
─────────────────────────────────────────────────────────────────
streamable_http_client(URL)               StreamableHTTPSessionManager
        │                                         │
        ▼                                         │
  (read, write, _) ◄──────────────────► session_manager.handle_request
        │                                         │
        ▼                                         ▼
  ClientSession(read, write)             Starlette app mounted at /mcp
        │
        ├─► session.initialize()  ──POST /mcp──►  handshake
        ├─► session.list_tools()  ──POST /mcp──►  handle_list_tools()
        │                         ◄──JSON list──   [Tool, Tool, ...]
        └─► session.call_tool()   ──POST /mcp──►  handle_call_tool()
                                  ◄──TextContent─  result JSON string
```

Each operation is a standard HTTP POST. "Streamable" means the server _can_ stream results via SSE for long-running tools — for short tools like ours, it's simple request/response.

### 3.6 The MCP Session Lifecycle

```
Terminal 1 — uv run python server.py

  uvicorn starts
    └─ Starlette app_lifespan runs
         └─ session_manager.run() starts
              └─ server_lifespan() yields {}
                   └─ server accepting connections at /mcp

Terminal 2 — uv run python main.py  (or test_interactive.py)

  async with streamable_http_client(URL) as (read, write, _):
    └─ TCP connection to :8001
       async with ClientSession(read, write) as session:
         await session.initialize()        ← MCP handshake
         get_mcp_tools(session)
           └─ session.list_tools()         ← fetch 6 tool descriptors
         build_graph(langchain_tools, ...)
           └─ LLM bound to 6 StructuredTools
         ...agent runs scenarios...
           each tool call → session.call_tool() → HTTP POST
       └─ session closed
    └─ TCP connection closed
```

---

## 4. Technology Deep-Dive: LangGraph

### 4.1 What Problem Does LangGraph Solve?

A basic AI agent needs a loop: call LLM → execute tools → feed results back → repeat until done. You can write this loop manually (ch06 does exactly that). As agents grow more complex the loop becomes a tangle of concerns — loop control mixed with tool execution mixed with state management.

LangGraph models the agent as a **directed graph**: each concern lives in its own node, routing is declared separately from logic, and the framework runs the loop.

### 4.2 The Manual Loop vs the Graph

```
ch06 — manual loop (concerns tangled):        LangGraph (concerns separated):
──────────────────────────────────────         ──────────────────────────────
while True:                                    graph.set_entry_point("agent")
  resp = llm.chat(messages, tools=tools)       graph.add_conditional_edges(
  if not resp.tool_calls:                        "agent", tools_condition)
    return resp.content   # exit              graph.add_edge("tools", "agent")
  messages.append(resp)
  for call in resp.tool_calls:
    result = execute_tool(call)
    messages.append(result)
  # back to top

Adding a logging step in ch06:  touch the loop body.
Adding a logging step in LangGraph:
  graph.add_node("logger", log_fn)
  graph.add_edge("tools", "logger")    # was "tools" → "agent"
  graph.add_edge("logger", "agent")
  # agent_node and tool_node: untouched
```

### 4.3 StateGraph, Nodes, and Edges

```
NODES — Python functions: receive state, return new partial state
─────────────────────────────────────────────────────────────────
def agent_node(state: MessagesState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}    # return ONLY the new message

EDGES — routing rules declared outside the node logic
─────────────────────────────────────────────────────────────────
graph.add_edge("tools", "agent")
  → after tools node, ALWAYS go to agent node

graph.add_conditional_edges("agent", tools_condition)
  → after agent node, CALL tools_condition(state):
      last msg has tool_calls?  → route to "tools"
      last msg has no calls?    → route to END

COMPILATION — locks the graph and makes it runnable
─────────────────────────────────────────────────────────────────
compiled = graph.compile()
result   = await compiled.ainvoke({"messages": [HumanMessage(...)]})
```

### 4.4 MessagesState and the add_messages Reducer

`MessagesState` is the built-in state type for chat agents. Its key property is the `add_messages` **reducer**:

```python
class MessagesState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
#                                          ^^^^^^^^^^^
#  This tells LangGraph: when a node returns {"messages": [new]},
#  APPEND it to the list — do NOT replace the whole list.
```

Each node only returns the new message(s) it produced — LangGraph handles the accumulation:

```
Initial:           [HumanMessage("screen flickering")]

agent iteration 1: returns [AIMessage(tool_calls=[search_tickets, get_user_profile])]
state becomes:     [Human, AI(tc1,tc2)]

tools executes:    returns [ToolMessage(search result), ToolMessage(profile result)]
state becomes:     [Human, AI(tc1,tc2), Tool(r1), Tool(r2)]

agent iteration 2: returns [AIMessage(tool_calls=[create_ticket])]
state becomes:     [Human, AI(tc1,tc2), Tool(r1), Tool(r2), AI(tc3)]

tools executes:    returns [ToolMessage(ticket created)]
state becomes:     [Human, AI(tc1,tc2), Tool(r1), Tool(r2), AI(tc3), Tool(r3)]

agent iteration 3: no tool_calls → returns [AIMessage("Ticket T-... created")]
state becomes:     [Human, AI(tc1,tc2), Tool(r1), Tool(r2), AI(tc3), Tool(r3), AI(final)]
→ tools_condition routes to END
```

### 4.5 ToolNode and tools_condition

**`ToolNode(tools)`** — given an `AIMessage` with `tool_calls`, it:

1. Finds the right `StructuredTool` by name
2. Validates arguments against the Pydantic `args_schema`
3. Calls the tool's async `_call()` function (which hits the MCP server)
4. Wraps the result in a `ToolMessage` and appends to state
5. Handles **parallel tool calls** automatically

**`tools_condition(state)`** — the conditional router:

- Last message has `tool_calls`? → return `"tools"`
- Last message has no tool calls? → return `END`

### 4.6 The ReAct Pattern

LangGraph implements **ReAct** (Reason + Act) — the standard architecture for tool-using agents:

```
┌──────────────────────────────────────────────────────┐
│                    ReAct Loop                        │
│                                                      │
│  REASON  — LLM looks at state, decides next action   │
│            (tool call or final answer)               │
│                                                      │
│  ACT     — ToolNode executes the requested tool(s)   │
│            and appends results to state              │
│                                                      │
│  OBSERVE — LLM sees tool results on next iteration   │
│            and reasons again                         │
│                                                      │
│  Repeats until LLM returns a message with no         │
│  tool_calls → tools_condition routes to END          │
└──────────────────────────────────────────────────────┘

In graph form:
  [START]
    → [agent: REASON]
        → tool calls? → [tools: ACT] → [agent: OBSERVE+REASON] → ...
        → no calls?   → [END]
```

---

## 5. The MCP ↔ LangGraph Bridge

This is the most important concept in the project. `client.py` converts between MCP's interface and LangChain's interface:

```
MCP world (from server.py)              LangGraph world (needed by graph.py)
────────────────────────────────────    ────────────────────────────────────
mcp_types.Tool                     →    BaseTool (StructuredTool)
  .name         (str)              →      .name         (str)
  .description  (str)              →      .description  (str)
  .inputSchema  (JSON Schema dict) →      .args_schema  (Pydantic model class)
  session.call_tool(**args)        →      ._call(**kwargs) → str
```

**Step 1: JSON Schema → Pydantic model** (for argument validation)

For `search_tickets`, `_json_schema_to_pydantic()` builds the equivalent of:

```python
class search_tickets(BaseModel):
    keyword: str    # required field (from JSON Schema "required" array)
```

**Step 2: Async closure over the live session** (for execution)

```python
def mcp_tool_to_langchain(tool, session):
    args_schema = _json_schema_to_pydantic(tool.inputSchema, tool.name)

    async def _call(**kwargs) -> str:        # captures tool.name and session
        result = await session.call_tool(name=tool.name, arguments=kwargs)
        return result.content[0].text

    return StructuredTool.from_function(
        coroutine=_call, name=tool.name,
        description=tool.description, args_schema=args_schema,
    )
```

**The full call chain when LangGraph invokes a tool:**

```
LangGraph ToolNode
  → StructuredTool.invoke({"keyword": "VPN"})
    → validates args against Pydantic model
    → calls _call(keyword="VPN")
      → session.call_tool("search_tickets", {"keyword": "VPN"})
        → HTTP POST to /mcp
          → server.handle_call_tool("search_tickets", {...})
            → search_tickets({"keyword": "VPN"})
              → returns [TextContent(text='{"match_count": 1, ...}')]
        → result.content[0].text = '{"match_count": 1, ...}'
      → returns the JSON string
    → ToolMessage(content='{"match_count": 1, ...}')
  → appended to MessagesState
```

LangGraph never knows it's talking to MCP. MCP never knows it's being called by LangGraph.

---

## 6. Project Architecture

### 6.1 Layer Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  ENTRY POINTS                                                    │
│  main.py — wires everything, runs 6 demo scenarios              │
│  test_interactive.py — REPL for manual testing (--verbose flag) │
└───────────────────────────┬──────────────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
┌──────────────────────┐   ┌─────────────────────────────────────┐
│  CLIENT LAYER        │   │  GRAPH LAYER                        │
│  client.py           │   │  graph.py                           │
│                      │   │                                     │
│  get_mcp_tools()     │   │  build_graph(tools, api_key)        │
│  Fetches tools via   │   │                                     │
│  MCP and converts    │   │  ┌─────────┐    ┌────────────────┐  │
│  to LangChain        │   │  │  agent  │───►│tools_condition │  │
│  StructuredTools     │   │  │  node   │    └──────┬─────────┘  │
│                      │   │  │  (LLM)  │          │yes         │
│  _json_schema        │   │  └────▲────┘   ┌──────▼─────────┐  │
│  _to_pydantic()      │   │       │        │  tool node     │  │
│  mcp_tool_to         │   │       └────────│  (ToolNode)    │  │
│  _langchain()        │   │                └────────────────┘  │
│                      │   │  no calls → END                     │
└──────────┬───────────┘   └─────────────────────────────────────┘
           │ session.call_tool()  (HTTP POST)
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  MCP SERVER LAYER                                                │
│  server.py — Low-level MCP server on port 8001                  │
│                                                                  │
│  handle_list_tools() → returns tool descriptors                  │
│  handle_call_tool()  → dispatches to correct handler            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  tools/__init__.py — Registry {name: {tool, handler}}    │   │
│  │  tools/tickets.py            tools/users.py              │   │
│  │   search_tickets              get_user_profile            │   │
│  │   create_ticket                                           │   │
│  │   update_ticket_status                                    │   │
│  │   list_open_tickets                                       │   │
│  │   add_comment                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────┐   ┌──────────────────────────────────────────┐ │
│  │  data.py    │   │  schema.py                               │ │
│  │  tickets[]  │   │  Ticket (id, title, status, comments...) │ │
│  │  users[]    │   │  UserProfile (email, sla_tier...)        │ │
│  └─────────────┘   └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 File Responsibility Map

| File                  | Responsibility                            | Depends on                    |
| --------------------- | ----------------------------------------- | ----------------------------- |
| `schema.py`           | Domain model definitions (Pydantic)       | nothing                       |
| `data.py`             | In-memory data store (module singleton)   | `schema.py`                   |
| `tools/tickets.py`    | 5 ticket MCP tools (3-part pattern each)  | `data.py`, `schema.py`        |
| `tools/users.py`      | 1 user-profile MCP tool                   | `data.py`                     |
| `tools/__init__.py`   | Tool registry dict                        | both `tools/*.py` files       |
| `server.py`           | Low-level MCP HTTP server                 | `tools/__init__.py`           |
| `client.py`           | MCP→LangChain conversion bridge           | `mcp`, `langchain_core`       |
| `graph.py`            | LangGraph agent graph definition          | `langchain_groq`, `langgraph` |
| `main.py`             | Entry point: 6 demo scenarios             | `client.py`, `graph.py`       |
| `test_interactive.py` | Interactive REPL + `--verbose` state view | `client.py`, `graph.py`       |

---

## 7. File-by-File Breakdown

### 7.1 `schema.py`

The domain model layer. Two Pydantic models used throughout the system:

```python
class UserProfile(BaseModel):
    email: str
    name: str
    department: str
    machine: str
    sla_tier: Literal["standard", "high", "critical"]

class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: f"T-{str(uuid.uuid4())[:6].upper()}")
    title: str
    description: str
    user_email: str
    priority: Literal["low", "medium", "high"]
    status: Literal["open", "in_progress", "resolved"] = "open"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(...))
    comments: list[dict] = Field(default_factory=list)
```

**Design decisions:**

- `Literal[...]` enforces valid values — invalid priority strings raise `ValidationError` before touching the data store
- `id` and `created_at` use `default_factory` — auto-generated on instantiation, no caller code needed
- `id` format `T-XXXXXX` is human-readable and short enough to display in chat
- `comments` is `list[dict]` — each entry is `{"timestamp": "...", "text": "..."}` appended by `add_comment`

### 7.2 `data.py`

The in-memory "database". Two module-level lists:

```python
user_profiles: list[UserProfile] = [alice, bob, carol]   # fixed
tickets: list[Ticket] = [vpn_ticket, outlook_ticket]     # 2 pre-seeded, grows at runtime
```

**The Python module singleton pattern:** When Python imports `data.py`, it creates exactly one module object. Every file that does `from data import tickets` gets a reference to the **same list**. When `create_ticket` appends a new `Ticket`, `search_tickets` immediately sees it — no database needed.

**Pre-seeded tickets:** `T-AA1B2C` (Bob's VPN issue) and `T-DD3E4F` (Alice's Outlook issue) let Scenarios 2 and 6 demonstrate duplicate-detection and comment-adding on existing tickets at startup.

### 7.3 `tools/tickets.py`

Five MCP tools covering the full ticket lifecycle. Each follows the 3-part pattern from Section 3.4:

| Tool                   | Input args                                 | What it does                                                           |
| ---------------------- | ------------------------------------------ | ---------------------------------------------------------------------- |
| `search_tickets`       | `keyword`                                  | Case-insensitive substring search in title + description               |
| `create_ticket`        | `title, description, user_email, priority` | Pydantic-validates then appends to `tickets[]`                         |
| `update_ticket_status` | `ticket_id, status`                        | Finds ticket by ID, mutates `.status` in place                         |
| `list_open_tickets`    | `priority_filter`                          | Filters `tickets[]` to status=open/in_progress, optionally by priority |
| `add_comment`          | `ticket_id, comment`                       | Appends `{"timestamp": ..., "text": ...}` to `ticket.comments`         |

**Why validation in `create_ticket` matters:**

```python
ticket = Ticket(**arguments)   # Pydantic validates here — may raise ValidationError
tickets.append(ticket)         # only reached if validation passed
```

The data store is never touched on invalid input.

**`update_ticket_status` demonstrates mutable in-memory state:**

```python
ticket = next((t for t in tickets if t.id == ticket_id), None)
old_status = ticket.status
ticket.status = new_status    # mutates the object in place — all readers see the change
```

### 7.4 `tools/users.py`

One MCP tool: `get_user_profile`. Case-insensitive email lookup returning the user's full profile as JSON.

The agent uses `sla_tier` to decide ticket priority:

- `critical` or `high` SLA → `high` priority
- `standard` SLA → `medium` or `low` priority

This is a key example of **multi-step reasoning**: the agent cannot choose the right priority without first knowing the user's SLA tier. It must call `get_user_profile` before `create_ticket`.

### 7.5 `tools/__init__.py` — The Registry

A plain dict mapping tool names to their descriptor and handler:

```python
tools = {
    "search_tickets":        {"tool": search_tickets_tool,        "handler": search_tickets},
    "create_ticket":         {"tool": create_ticket_tool,         "handler": create_ticket},
    "update_ticket_status":  {"tool": update_ticket_status_tool,  "handler": update_ticket_status},
    "list_open_tickets":     {"tool": list_open_tickets_tool,     "handler": list_open_tickets},
    "add_comment":           {"tool": add_comment_tool,           "handler": add_comment},
    "get_user_profile":      {"tool": get_user_profile_tool,      "handler": get_user_profile},
}
```

`server.py` iterates this dict in both `handle_list_tools` and `handle_call_tool`. **To add a new tool:** create descriptor + handler in the appropriate file, add one entry here. `server.py` and `client.py` need zero changes.

### 7.6 `server.py`

The low-level MCP server. Mirrors ch06's `server.py` — the only real differences are the server name, port, and which `tools/` package is imported:

```python
server = Server("it-support-server", lifespan=server_lifespan)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [entry["tool"] for entry in tools.values()]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name not in tools:
        raise ValueError(f"Unknown tool: {name}")
    return await tools[name]["handler"](arguments)

session_manager = StreamableHTTPSessionManager(server)
app = Starlette(routes=[Mount("/mcp", app=session_manager.handle_request)], ...)
```

The entire HTTP-stream architecture is reusable across projects.

### 7.7 `client.py`

The MCP ↔ LangGraph bridge — the most novel file in the project. See Section 5 for the full deep-dive.

Key functions:

- **`_json_schema_to_pydantic(schema, name)`** — converts a JSON Schema dict into a `pydantic.create_model()` class for argument validation
- **`mcp_tool_to_langchain(tool, session)`** — wraps a `types.Tool` as a `StructuredTool` with an async closure that calls `session.call_tool()` at runtime
- **`get_mcp_tools(session)`** — calls `session.list_tools()` and returns a list of converted `StructuredTool` objects ready for LangGraph

### 7.8 `graph.py`

The LangGraph graph definition. This file replaces the entire `while True` loop from ch06:

```python
def build_graph(tools: list[BaseTool], api_key: str) -> CompiledGraph:
    llm = ChatGroq(model=GROQ_MODEL, api_key=api_key)
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState) -> dict:
        iteration = sum(1 for m in state["messages"] if m.type == "ai") + 1
        print(f"\n  [agent] iteration {iteration}...")
        messages = [SystemMessage(SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        if response.tool_calls:
            print(f"  [agent] tool calls: {[tc['name'] for tc in response.tool_calls]}")
        return {"messages": [response]}

    tool_node = ToolNode(tools)

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()
```

**`llm.bind_tools(tools)`** — serialises the `StructuredTool` list into the format Groq's API expects so the LLM can request tools by name.

**`SystemMessage` prepended on every call** — `MessagesState` only stores `Human/AI/Tool` messages, not the system prompt. Prepending it every iteration ensures the LLM always has its instructions regardless of how many tool rounds have passed.

**Verbose logging** — every `agent_node` call prints the iteration number, and either the tool names requested or a preview of the final answer. This lets you watch the ReAct loop execute in real time.

### 7.9 `main.py`

The entry point. Wires everything together and runs 6 demo scenarios:

```python
async with streamable_http_client(SERVER_URL) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        langchain_tools = await get_mcp_tools(session)
        graph = build_graph(langchain_tools, api_key)
        for label, user_input in DEMO_REQUESTS:
            await run_scenario(graph, label, user_input)
```

The `async with` blocks keep the MCP session alive for all 6 scenarios — tools are fetched once, the graph is built once, and `session.call_tool()` is reused for every tool invocation.

**Six scenarios exercise every tool and every graph path:**

| #   | User              | Request                         | Tools exercised               |
| --- | ----------------- | ------------------------------- | ----------------------------- |
| 1   | alice@company.com | Screen flickering (NEW)         | search → get_profile → create |
| 2   | bob@company.com   | VPN drops (DUPLICATE)           | search → finds T-AA1B2C → END |
| 3   | carol@company.com | Printer offline (NEW)           | search → get_profile → create |
| 4   | bob@company.com   | VPN fixed, resolve it           | update_status → add_comment   |
| 5   | IT manager        | Show open high-priority tickets | list_open_tickets             |
| 6   | alice@company.com | Add note to existing ticket     | search → add_comment          |

**`test_interactive.py`** provides an interactive REPL for the same graph. Run with `--verbose` to see the full `MessagesState` after each turn — ideal for learning how state accumulates.
