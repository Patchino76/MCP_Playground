# How client_v1.py Works

## Overview

`client_v1.py` is a **direct MCP tool client** that connects to an MCP server and calls tools directly - no LLM involved. This is the foundational pattern you need to understand before adding AI on top.

Think of it like this: Instead of asking an AI to use tools for you, **you use the tools yourself**.

---

## The Big Picture

```
┌─────────────────┐         HTTP          ┌─────────────────┐
│  client_v1.py   │◄─────────────────────►│   MCP Server    │
│                 │   Streamable HTTP     │                 │
│                 │      Transport        │                 │
└─────────────────┘                       └─────────────────┘
        │                                          │
        │ 1. Connect                               │
        │ 2. Handshake                              │
        │ 3. List tools                             │
        │ 4. Call tools                             │
        └──────────────────────────────────────────┘
```

**Key Idea**: The client and server communicate using the **MCP (Model Context Protocol)** over HTTP. This protocol defines how to:
- Discover what tools are available
- Call those tools with arguments
- Get results back

---

## Architecture Breakdown

### The Three-Layer Stack

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Code (main())                       │
│  - Orchestrates the workflow                                 │
│  - Calls demo functions                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ClientSession (session)                     │
│  - High-level MCP client interface                           │
│  - Methods: initialize(), list_tools(), call_tool()          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            streamable_http_client (transport)                │
│  - Handles HTTP communication                               │
│  - Manages read/write streams                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (HTTP endpoint)                │
│  - Receives MCP protocol messages                             │
│  - Executes tools and returns results                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Execution Flow

### Step 1: Connection Setup

```python
async with streamable_http_client(SERVER_URL) as (read, write, _):
    async with ClientSession(read, write) as session:
```

What happens:

```
client_v1.py                    streamable_http_client
     │                                  │
     │  1. Create HTTP connection      │
     │─────────────────────────────────►│
     │                                  │
     │  2. Get read/write streams      │
     │◄────────────────────────────────│
     │  (read, write, _)               │
     │                                  │
     │  3. Create ClientSession        │
     │─────────────────────────────────►│
     │                                  │
     │  4. Ready to use session        │
     │◄────────────────────────────────│
```

**Key Concepts**:
- `streamable_http_client`: Creates an HTTP connection to the MCP server
- Returns three things: `read_stream`, `write_stream`, and `_` (cleanup callback)
- `ClientSession`: Wraps the streams and provides the MCP protocol methods

---

### Step 2: Handshake

```python
init_result = await session.initialize()
```

What happens:

```
Client                          Server
  │                               │
  │  1. Send client capabilities  │
  │──────────────────────────────►│
  │  (what I can do)              │
  │                               │
  │  2. Send server capabilities  │
  │◄──────────────────────────────│
  │  (what I can do)              │
  │                               │
  │  3. Server info returned      │
  │◄──────────────────────────────│
  │  {name, version}              │
```

**Key Concepts**:
- **Handshake**: First step in any MCP connection
- Both sides announce what they support
- Server returns its name and version
- Required before any other MCP operations

---

### Step 3: List Tools

```python
result = await session.list_tools()
for tool in result.tools:
    print(f"Tool: {tool.name}")
    print(f"Description: {tool.description}")
    print(f"Input Schema: {tool.inputSchema}")
```

What happens:

```
Client                          Server
  │                               │
  │  1. Request tool list         │
  │──────────────────────────────►│
  │                               │
  │  2. Return tool definitions   │
  │◄──────────────────────────────│
  │  [                           │
  │    {                         │
  │      name: "get_customer",   │
  │      description: "...",     │
  │      inputSchema: {...}      │
  │    },                        │
  │    {                         │
  │      name: "get_orders",     │
  │      ...                     │
  │    }                         │
  │  ]                           │
```

**Key Concepts**:
- **Tool Discovery**: Client learns what tools are available
- **Input Schema**: JSON Schema describing what arguments a tool accepts
- **Required vs Optional**: Schema marks which parameters are required

Example schema:
```json
{
  "type": "object",
  "properties": {
    "customer_id": {
      "type": "integer",
      "description": "The customer ID"
    }
  },
  "required": ["customer_id"]
}
```

---

### Step 4: Call a Tool

```python
result = await session.call_tool(
    name="get_customer",
    arguments={"customer_id": 101},
)
```

What happens:

```
Client                          Server
  │                               │
  │  1. Call tool with args      │
  │──────────────────────────────►│
  │  {                           │
  │    name: "get_customer",     │
  │    arguments: {              │
  │      customer_id: 101        │
  │    }                         │
  │  }                           │
  │                               │
  │  2. Execute tool logic        │
  │                               │
  │  3. Return result             │
  │◄──────────────────────────────│
  │  {                           │
  │    isError: false,           │
  │    content: [                │
  │      {                       │
  │        type: "text",         │
  │        text: "{\"id\":101...}"│
  │      }                       │
  │    ]                         │
  │  }                           │
```

**Key Concepts**:
- **CallToolResult**: Response object with two important fields:
  - `isError`: Boolean indicating if the call failed
  - `content`: List of content blocks (text, images, etc.)
- **Content Blocks**: MCP can return multiple types of content
- **JSON Text Response**: This server returns JSON as a text string

---

## Error Handling

```python
if result.isError:
    print(f"ERROR: {result.content[0].text}")
    return
```

What happens when something goes wrong:

```
Client                          Server
  │                               │
  │  1. Call tool with bad ID    │
  │──────────────────────────────►│
  │  {customer_id: 999}          │
  │                               │
  │  2. Tool not found            │
  │                               │
  │  3. Return error              │
  │◄──────────────────────────────│
  │  {                           │
  │    isError: true,            │
  │    content: [                │
  │      {                       │
  │        type: "text",         │
  │        text: "Customer not   │
  │               found"          │
  │      }                       │
  │    ]                         │
  │  }                           │
```

**Key Concepts**:
- Errors are returned, not thrown
- Always check `result.isError`
- Error message is in `result.content[0].text`

---

## The Demo Functions

### demo_list_tools()

**Purpose**: Show what tools are available

```
Input:  session (ClientSession)
Output: Prints tool list to console

Flow:
  1. Call session.list_tools()
  2. Iterate over result.tools
  3. Print name, description, and schema
  4. Mark required parameters with "*"
```

### demo_get_customer()

**Purpose**: Get customer information by ID

```
Input:  session, customer_id
Output: Prints customer data or error

Flow:
  1. Call session.call_tool() with name and arguments
  2. Check result.isError
  3. If error, print message and return
  4. Parse JSON from result.content[0].text
  5. Pretty-print the data
```

### demo_get_orders()

**Purpose**: Get order history for a customer

```
Input:  session, customer_id
Output: Prints order list or error

Flow:
  1. Same pattern as demo_get_customer()
  2. Parse JSON response
  3. Print summary and order descriptions
```

---

## Complete Execution Timeline

```
Time  →
│
│     [START]
│        │
│        ▼
│     ┌──────────────┐
│     │ Connect to   │◄─────────────────────────────┐
│     │   Server     │                               │
│     └──────┬───────┘                               │
│            │                                       │
│            ▼                                       │
│     ┌──────────────┐                               │
│     │   Handshake  │                               │
│     └──────┬───────┘                               │
│            │                                       │
│            ▼                                       │
│     ┌──────────────┐                               │
│     │ List Tools   │                               │
│     └──────┬───────┘                               │
│            │                                       │
│            ▼                                       │
│     ┌──────────────┐                               │
│     │ get_customer │◄──────────┐                   │
│     │  (id=101)    │            │                   │
│     └──────┬───────┘            │                   │
│            │                    │                   │
│            ▼                    │                   │
│     ┌──────────────┐            │                   │
│     │ get_customer │            │                   │
│     │  (id=999)    │            │                   │
│     └──────┬───────┘            │                   │
│            │                    ▼                   │
│            ▼              ┌──────────┐              │
│     ┌──────────────┐      │   END    │              │
│     │ get_orders   │      └──────────┘              │
│     │  (id=101)    │                                 │
│     └──────┬───────┘                                 │
│            │                                         │
│            ▼                                         │
│     ┌──────────────┐                                 │
│     │ get_orders   │                                 │
│     │  (id=102)    │                                 │
│     └──────┬───────┘                                 │
│            │                                         │
│            ▼                                         │
│     ┌──────────────┐                                 │
│     │   Cleanup    │◄────────────────────────────────┘
│     └──────┬───────┘
│            │
│            ▼
│        [END]
```

---

## Key MCP Concepts Explained

### 1. Transport Layer

**What it is**: The communication channel between client and server.

**Why it matters**: MCP can work over different transports (stdio, HTTP, WebSocket). This client uses **Streamable HTTP**.

**Analogy**: Like choosing between phone, email, or video call - same conversation, different medium.

### 2. Session

**What it is**: A high-level object that manages the MCP protocol.

**Why it matters**: You don't deal with raw protocol messages. Just call methods like `list_tools()`.

**Analogy**: Like a translator - you speak Python, it speaks MCP protocol.

### 3. Tools

**What they are**: Functions the server exposes that you can call.

**Why they matter**: This is how you interact with the server's capabilities.

**Analogy**: Like a restaurant menu - you see what's available and order what you want.

### 4. Content Blocks

**What they are**: Structured data returned by tools.

**Why they matter**: MCP supports multiple content types (text, images, audio, etc.).

**Analogy**: Like a multimedia message - can contain text, images, or both.

### 5. JSON Schema

**What it is**: Standard way to describe data structure.

**Why it matters**: Tells you what arguments a tool needs and what format.

**Analogy**: Like a form with labeled fields - you know what to fill in.

---

## Why No LLM?

This client is **direct** - no AI involved. Why?

1. **Understanding First**: Learn the MCP protocol before adding complexity
2. **Predictable**: Same input always gives same output
3. **Debuggable**: Easy to trace what's happening
4. **Foundation**: LLM clients build on this pattern

**Next Step**: Add an LLM that uses these tools to answer questions!

---

## Summary

`client_v1.py` demonstrates the core MCP pattern:

```
1. Connect → streamable_http_client()
2. Handshake → session.initialize()
3. Discover → session.list_tools()
4. Execute  → session.call_tool()
5. Handle   → Check result.isError
```

**The key insight**: MCP is just a protocol for calling remote tools. Once you understand this pattern, adding an LLM is just another layer on top.
