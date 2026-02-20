# lg_mcp_01 — IT Support Ticket Assistant
## Part 1: Architecture, Concepts & File Breakdown

> **Part 2** covers end-to-end information flow, execution traces, state evolution, and extension ideas.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [Key Concepts](#3-key-concepts)
   - 3.1 [Model Context Protocol (MCP)](#31-model-context-protocol-mcp)
   - 3.2 [Streamable HTTP Transport](#32-streamable-http-transport)
   - 3.3 [Low-Level MCP Server](#33-low-level-mcp-server)
   - 3.4 [LangGraph StateGraph](#34-langgraph-stategraph)
   - 3.5 [MessagesState and Reducers](#35-messagesstate-and-reducers)
   - 3.6 [ToolNode and tools_condition](#36-toolnode-and-tools_condition)
4. [File-by-File Breakdown](#4-file-by-file-breakdown)
   - 4.1 [schema.py](#41-schemapy)
   - 4.2 [data.py](#42-datapy)
   - 4.3 [tools/tickets.py](#43-toolsticketspy)
   - 4.4 [tools/users.py](#44-toolsuserspy)
   - 4.5 [tools/__init__.py](#45-tools__init__py)
   - 4.6 [server.py](#46-serverpy)
   - 4.7 [client.py](#47-clientpy)
   - 4.8 [graph.py](#48-graphpy)
   - 4.9 [main.py](#49-mainpy)

---

## 1. Project Overview

This project is a **minimal but complete agentic system** that demonstrates how to combine two modern AI infrastructure technologies:

- **MCP (Model Context Protocol)** — a standard for exposing tools to AI agents over HTTP
- **LangGraph** — a framework for building stateful, multi-step AI agents as graphs

The domain is an **IT Support Ticket Assistant**. A user describes a technical problem in plain English. The agent autonomously:

1. Searches for duplicate tickets
2. Looks up the user's SLA tier
3. Creates a new ticket with the correct priority (or reports the duplicate)
4. Returns a structured natural language summary

The project is designed as a **learning exercise**. Every design decision is explained, and the code is intentionally kept minimal so each concept is visible without noise.

---

## 2. Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                 │
│  Opens MCP session → fetches tools → builds graph → runs demo  │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌─────────────────┐           ┌──────────────────────┐
│   client.py     │           │      graph.py         │
│                 │           │                       │
│ get_mcp_tools() │           │  build_graph()        │
│                 │           │                       │
│ Converts MCP    │           │  StateGraph with:     │
│ tools into      │           │  - agent_node (LLM)   │
│ LangChain       │           │  - tool_node (MCP)    │
│ StructuredTools │           │  - conditional edges  │
└────────┬────────┘           └──────────┬────────────┘
         │  tools list                   │ compiled graph
         └──────────────┬────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │   LangGraph      │
              │   Execution      │
              │                  │
              │  agent ──────────┤ tool_calls?
              │    ▲      YES    ├──────────────┐
              │    │             │              ▼
              │    └─────────────┤           tools
              │          NO      │              │
              │          ▼       │              │
              │         END      │◄─────────────┘
              └──────────────────┘
                        │
                        │ session.call_tool()
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                       server.py                                 │
│              Low-level MCP Server (port 8001)                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   tools/ registry                        │   │
│  │  search_tickets │ create_ticket │ get_user_profile       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────┐    ┌──────────────────────────────────────┐   │
│  │  data.py    │    │  schema.py                           │   │
│  │  tickets[]  │    │  Ticket, UserProfile (Pydantic)      │   │
│  │  users[]    │    └──────────────────────────────────────┘   │
│  └─────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Concepts

### 3.1 Model Context Protocol (MCP)

MCP is an open standard (by Anthropic) that defines how AI clients and tool servers communicate. Think of it as a USB standard for AI tools — any MCP client can talk to any MCP server without custom integration code.

**Core primitives:**

| Primitive | Description |
|-----------|-------------|
| `Tool` | A named function with a JSON Schema input definition |
| `list_tools` | Client asks server: "what tools do you have?" |
| `call_tool` | Client asks server: "run this tool with these arguments" |
| `TextContent` | The standard return type: a block of text |

**In this project:**
- The server exposes 3 tools: `search_tickets`, `create_ticket`, `get_user_profile`
- The client fetches them via `session.list_tools()` at startup
- The LangGraph `ToolNode` executes them via `session.call_tool()` at runtime

### 3.2 Streamable HTTP Transport

MCP supports multiple transports. This project uses **Streamable HTTP**, the modern production transport (introduced in MCP spec 2025-03-26).

```
Client                              Server
  │                                   │
  │── POST /mcp (initialize) ────────►│
  │◄─ 200 OK (server capabilities) ───│
  │                                   │
  │── POST /mcp (list_tools) ────────►│
  │◄─ 200 OK (tool list) ─────────────│
  │                                   │
  │── POST /mcp (call_tool) ─────────►│
  │◄─ 200 OK (tool result) ───────────│
```

Each request is a standard HTTP POST. The "streamable" part means the server *can* stream results back via SSE (Server-Sent Events) for long-running tools — but for our simple tools, it's just request/response.

**Key classes:**
- `streamable_http_client(url)` — opens the transport on the client side
- `StreamableHTTPSessionManager` — manages sessions on the server side
- `ClientSession` — the object you use to make MCP calls (`list_tools`, `call_tool`)

### 3.3 Low-Level MCP Server

MCP provides two server APIs:

| API | Description | Use when |
|-----|-------------|----------|
| High-level (`FastMCP`) | Decorator-based, minimal boilerplate | Quick prototyping |
| Low-level (`Server`) | Explicit handlers, full control | Production, learning |

This project uses the **low-level API** — the same as ch06. The pattern is:

```python
server = Server("server-name", lifespan=lifespan_fn)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]: ...

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]: ...
```

The server is then wrapped in a `StreamableHTTPSessionManager` and mounted on a Starlette app. This gives you a production-ready HTTP server with zero framework magic.

**Lifecycle:**
```
uvicorn starts
    └─ Starlette app_lifespan begins
         └─ session_manager.run() starts
              └─ server_lifespan yields {}
                   └─ server accepts connections at /mcp
```

### 3.4 LangGraph StateGraph

LangGraph models an agent as a **directed graph** where:
- **Nodes** are Python functions that transform state
- **Edges** define the routing between nodes
- **State** is a typed dict that accumulates data across the entire run

```python
StateGraph(StateType)
    .add_node("name", function)
    .add_edge("from", "to")
    .add_conditional_edges("from", router_function)
    .set_entry_point("start_node")
    .compile()
```

The compiled graph is invoked with an initial state and runs until it reaches `END`.

**Why this matters:** In ch06, the developer writes the loop. In LangGraph, the developer writes the nodes and edges — the framework runs the loop. This separation makes complex multi-step agents much easier to reason about, debug, and extend.

### 3.5 MessagesState and Reducers

`MessagesState` is LangGraph's built-in state type for chat agents:

```python
class MessagesState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

The `add_messages` annotation is a **reducer** — a function that tells LangGraph how to merge new state into existing state. Instead of replacing the messages list, `add_messages` *appends* to it.

This means every node only needs to return the *new* messages it produced:

```python
def agent_node(state: MessagesState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}  # LangGraph appends — does NOT replace
```

After 3 iterations, `state["messages"]` contains the full conversation history automatically.

### 3.6 ToolNode and tools_condition

These are pre-built LangGraph components that implement the standard ReAct pattern:

**`ToolNode(tools)`**
- Reads `tool_calls` from the last `AIMessage` in state
- Calls each matching tool (by name) with the provided arguments
- Appends `ToolMessage` results back into state
- Handles parallel tool calls automatically

**`tools_condition(state)`**
- A router function for `add_conditional_edges`
- Returns `"tools"` if the last message has `tool_calls`
- Returns `END` if the last message has no `tool_calls`

Together they implement the entire tool-use loop without any custom code:

```python
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
```

---

## 4. File-by-File Breakdown

### 4.1 `schema.py`

Defines the two Pydantic domain models.

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
```

**Key design decisions:**
- `Literal[...]` types enforce valid values at the Pydantic level — invalid priority strings raise `ValidationError` before reaching the data store
- `id` and `created_at` use `default_factory` — auto-generated on instantiation, no caller code needed
- `Ticket.id` format `T-XXXXXX` is human-readable and short enough to display in chat

### 4.2 `data.py`

The in-memory "database". Two module-level lists that are mutated at runtime:

```python
user_profiles: list[UserProfile] = [...]   # 3 users, fixed
tickets: list[Ticket] = [...]              # 2 pre-seeded, grows at runtime
```

**Why module-level lists?**
When Python imports `data.py`, it creates one module object. Every other file that does `from data import tickets` gets a reference to the *same list object*. So when `create_ticket` appends to `tickets`, `search_tickets` immediately sees the new entry. This is Python's module singleton pattern — simple and effective for in-memory state.

**Pre-seeded tickets** serve a specific demo purpose: Scenario 2 (Bob's VPN issue) needs a duplicate to exist at startup so the agent can find it.

### 4.3 `tools/tickets.py`

Two MCP tools. Each follows the same three-part pattern:

```
1. input_schema dict  →  JSON Schema (what arguments the tool accepts)
2. types.Tool object  →  MCP tool descriptor (name + description + schema)
3. async handler fn   →  the actual implementation
```

**`search_tickets`** — keyword search:
```python
matches = [t for t in tickets
           if keyword in t.title.lower() or keyword in t.description.lower()]
```
Case-insensitive substring match. Returns a JSON dict with match count and ticket summaries.

**`create_ticket`** — creates and persists a ticket:
```python
ticket = Ticket(**arguments)   # Pydantic validates here
tickets.append(ticket)         # persists to the module-level list
```
Validation happens at the Pydantic layer before any mutation — if arguments are invalid, the list is never touched.

### 4.4 `tools/users.py`

One MCP tool: `get_user_profile`.

```python
match = next((u for u in user_profiles if u.email.lower() == email), None)
```

Case-insensitive email lookup. Returns the user's full profile as JSON. The agent uses `sla_tier` to decide ticket priority:
- `critical` or `high` SLA → `high` priority ticket
- `standard` SLA → `medium` or `low` priority ticket

This is a key example of **multi-step reasoning**: the agent cannot set the right priority without first knowing the user's SLA tier. It *must* call `get_user_profile` before `create_ticket`.

### 4.5 `tools/__init__.py`

The tool registry — a plain dict that maps tool names to their descriptor and handler:

```python
tools = {
    "search_tickets":   {"tool": search_tickets_tool,   "handler": search_tickets},
    "create_ticket":    {"tool": create_ticket_tool,    "handler": create_ticket},
    "get_user_profile": {"tool": get_user_profile_tool, "handler": get_user_profile},
}
```

`server.py` iterates this dict in both handlers. **Adding a new tool** requires only: (1) create the handler + descriptor in a new file, (2) add one entry to this dict. `server.py` and `client.py` need zero changes.

### 4.6 `server.py`

The MCP server. Intentionally mirrors ch06's `server.py` to show the pattern is reusable:

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

Compare with ch06's `server.py` — the only real differences are the server name (`"it-support-server"` vs `"marketing-server"`), the port (`8001` vs `8000`), and which `tools/` package is imported. The entire HTTP-stream architecture is copy-paste reusable.

### 4.7 `client.py`

The MCP ↔ LangGraph bridge. The most novel file in the project.

**Problem:** LangGraph's `ToolNode` expects `BaseTool` objects (LangChain interface). MCP gives us `types.Tool` descriptors and `ClientSession.call_tool()`. These two worlds need to be connected.

**Solution:** `mcp_tool_to_langchain()` wraps each MCP tool as a `StructuredTool`:

```python
def mcp_tool_to_langchain(tool: mcp_types.Tool, session: ClientSession) -> BaseTool:

    args_schema = _json_schema_to_pydantic(tool.inputSchema, model_name=tool.name)

    async def _call(**kwargs) -> str:
        result = await session.call_tool(name=tool.name, arguments=kwargs)
        return result.content[0].text

    return StructuredTool.from_function(
        coroutine=_call,
        name=tool.name,
        description=tool.description,
        args_schema=args_schema,
    )
```

The `_call` closure **captures `session`** — a reference to the live `ClientSession`. When LangGraph calls the tool, `_call` executes and the MCP request goes to the server transparently. **LangGraph never knows it's talking to MCP.**

**`_json_schema_to_pydantic()`** converts the MCP tool's JSON Schema into a Pydantic model class using `pydantic.create_model()`. LangGraph's `ToolNode` uses this to validate arguments before calling the tool.

**The conversion pipeline:**

```
mcp_types.Tool
    │
    ├─ .inputSchema (JSON Schema dict)
    │       │
    │       ▼
    │   _json_schema_to_pydantic()
    │       │
    │       ▼
    │   Pydantic model class  ──► args_schema
    │
    └─ .name, .description
            │
            ▼
        StructuredTool.from_function(
            coroutine  = _call,        ← async closure over session
            name       = tool.name,
            description= tool.description,
            args_schema= args_schema,
        )
            │
            ▼
        BaseTool  ◄── LangGraph ToolNode uses this directly
```

### 4.8 `graph.py`

The LangGraph graph definition. This file replaces the entire `while True` loop from ch06.

```python
def build_graph(tools: list[BaseTool], api_key: str) -> CompiledGraph:

    llm = ChatGroq(model=GROQ_MODEL, api_key=api_key)
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState) -> dict:
        messages = [SystemMessage(SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
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

**`llm.bind_tools(tools)`** — tells the LLM which tools are available. Internally, LangChain serializes the `StructuredTool` list into the format the Groq API expects (same JSON structure as ch06's `mcp_tool_to_groq()`). The LLM can then request tools by name in its response.

**`agent_node`** — prepends the `SystemMessage` on every call. This ensures the LLM always has its instructions even after multiple tool rounds, because `MessagesState` only stores `HumanMessage`, `AIMessage`, and `ToolMessage` — not the system prompt.

**`ToolNode(tools)`** — pre-built node. When the agent returns an `AIMessage` with `tool_calls`, this node:
1. Finds the matching `StructuredTool` by name
2. Calls `tool._call(**args)` — which hits the MCP server via the closure
3. Wraps the result in a `ToolMessage`
4. Returns `{"messages": [ToolMessage(...)]}`

### 4.9 `main.py`

The entry point. Wires everything together and runs the demo.

```python
async with streamable_http_client(SERVER_URL) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()

        langchain_tools = await get_mcp_tools(session)   # client.py
        graph = build_graph(langchain_tools, api_key)    # graph.py

        for label, user_input in DEMO_REQUESTS:
            final_state = await graph.ainvoke(
                {"messages": [HumanMessage(content=user_input)]}
            )
            print(final_state["messages"][-1].content)
```

**Lifetime of the MCP session:** The `async with` blocks keep the session open for the entire demo. All three scenarios share the same session — tools are fetched once, the graph is built once, and `session.call_tool()` is reused for every tool invocation across all scenarios.

**`graph.ainvoke()`** — the async version of `graph.invoke()`. It runs the full graph to completion and returns the final state. The caller doesn't see any of the intermediate steps — just the initial input and the final `MessagesState`.

**Three demo scenarios** are designed to exercise both graph paths:

| Scenario | User | Issue | Expected path |
|----------|------|-------|---------------|
| 1 | alice@company.com | Screen flickering (NEW) | search → profile → create → END |
| 2 | bob@company.com | VPN drops (DUPLICATE) | search → finds T-AA1B2C → END |
| 3 | carol@company.com | Printer offline (NEW) | search → profile → create → END |
