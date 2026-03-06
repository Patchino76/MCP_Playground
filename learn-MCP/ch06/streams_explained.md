# How Read/Write Streams Work in MCP

## Overview

The `read` and `write` streams are the **communication channels** between your client and the MCP server. They're the physical pipes that data flows through.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Your Code                               │
│                    (session.initialize(), etc.)                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ClientSession                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  send_request()  →  writes to write_stream                │  │
│  │  receive_response() ← reads from read_stream              │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   streamable_http_client                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  write_stream  →  HTTP POST to server                    │  │
│  │  read_stream   ←  HTTP response from server              │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Server                               │
│                    (localhost:8000/mcp)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Are Streams?

**Streams** are objects that let you read and write data sequentially. Think of them like pipes:

```
Write Stream:  [Your Data] ───► [Server]
Read Stream:   [Server] ────► [Your Data]
```

In MCP, these are **async streams** - they work with `async/await` because network I/O is asynchronous.

---

## How They're Created

```python
async with streamable_http_client(SERVER_URL) as (read, write, _):
```

When you call `streamable_http_client()`, it:

1. **Opens an HTTP connection** to the server
2. **Creates two async generators**:
   - `read`: An async iterator that yields incoming data
   - `write`: An async function that sends outgoing data
3. **Returns a cleanup callback** (the third `_` value)

```python
# Inside streamable_http_client (simplified):

async def streamable_http_client(url):
    # 1. Open HTTP connection
    http_client = httpx.AsyncClient()
    
    # 2. Create write stream (async function)
    async def write(message):
        # Send message via HTTP POST
        response = await http_client.post(url, json=message)
        return response
    
    # 3. Create read stream (async generator)
    async def read():
        # Read messages from HTTP responses
        async for response in http_client.stream(url):
            yield response.json()
    
    # 4. Return streams and cleanup
    yield read, write, lambda: http_client.close()
```

---

## How ClientSession Uses Them

```python
async with ClientSession(read, write) as session:
```

The `ClientSession` wraps the streams and provides a high-level API:

```
When you call:           What happens internally:
─────────────────────────────────────────────────────────────
session.initialize()    1. Write handshake request to write_stream
                        2. Read response from read_stream
                        3. Parse and return result

session.list_tools()     1. Write list_tools request to write_stream
                        2. Read response from read_stream
                        3. Parse and return tool list

session.call_tool()      1. Write tool call to write_stream
                        2. Read response from read_stream
                        3. Parse and return result
```

---

## Data Flow Example: Handshake

Let's trace what actually happens when you call `session.initialize()`:

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: ClientSession writes handshake request                  │
└─────────────────────────────────────────────────────────────────┘

Your code:
    init_result = await session.initialize()

ClientSession does:
    1. Build handshake message:
       {
         "jsonrpc": "2.0",
         "id": 1,
         "method": "initialize",
         "params": {
           "protocolVersion": "2024-11-05",
           "capabilities": {...},
           "clientInfo": {...}
         }
       }
    
    2. Write to write_stream:
       await write_stream(handshake_message)
    
    3. This sends HTTP POST to server:
       POST http://localhost:8000/mcp
       Content-Type: application/json
       Body: {handshake_message}


┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Server processes request                                │
└─────────────────────────────────────────────────────────────────┘

Server receives HTTP POST, processes it, and returns:
    {
      "jsonrpc": "2.0",
      "id": 1,
      "result": {
        "serverInfo": {
          "name": "demo-server",
          "version": "1.0.0"
        },
        "capabilities": {...}
      }
    }


┌─────────────────────────────────────────────────────────────────┐
│ Step 3: ClientSession reads response                            │
└─────────────────────────────────────────────────────────────────┘

ClientSession does:
    1. Read from read_stream:
       response = await read_stream()
    
    2. Parse JSON-RPC response
    
    3. Extract result and return:
       return InitializeResult(
           serverInfo=ServerInfo(name="demo-server", version="1.0.0"),
           capabilities=...
       )


┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Your code receives result                               │
└─────────────────────────────────────────────────────────────────┘

Your code:
    print(f"Server name: {init_result.serverInfo.name}")
    print(f"Server version: {init_result.serverInfo.version}")
```

---

## The Stream Interface

### Write Stream

```python
async def write(message: dict) -> None:
    """
    Send a message to the server.
    
    Args:
        message: JSON-RPC message as a dict
    """
    # Implementation sends via HTTP POST
```

**Usage by ClientSession**:
```python
await write_stream({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {...}
})
```

### Read Stream

```python
async def read() -> dict:
    """
    Read a message from the server.
    
    Returns:
        JSON-RPC response as a dict
    """
    # Implementation reads from HTTP response
```

**Usage by ClientSession**:
```python
response = await read_stream()
# response is like:
# {
#   "jsonrpc": "2.0",
#   "id": 1,
#   "result": {...}
# }
```

---

## Why This Abstraction?

### Problem: Raw HTTP is messy

```python
# Without streams - you'd write this every time:
async def call_tool_raw(tool_name, args):
    # 1. Build request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": args}
    }
    
    # 2. Send HTTP
    response = await http_client.post(url, json=request)
    
    # 3. Parse response
    data = response.json()
    
    # 4. Handle errors
    if "error" in data:
        raise Exception(data["error"])
    
    return data["result"]
```

### Solution: Streams + ClientSession

```python
# With streams - clean and simple:
result = await session.call_tool(
    name="get_customer",
    arguments={"customer_id": 101}
)
```

**Benefits**:
- **Separation of concerns**: Streams handle transport, ClientSession handles protocol
- **Testability**: Can mock streams for testing
- **Flexibility**: Different transports (HTTP, stdio) provide same stream interface
- **Simplicity**: You work with high-level methods, not raw HTTP

---

## Stream Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Connection Established                                        │
└─────────────────────────────────────────────────────────────────┘
    streamable_http_client() called
    └─> Creates read_stream, write_stream
    └─> Returns them to caller


┌─────────────────────────────────────────────────────────────────┐
│ 2. Session Created                                               │
└─────────────────────────────────────────────────────────────────┘
    ClientSession(read, write) created
    └─> Stores streams as instance variables
    └─> Ready to send/receive messages


┌─────────────────────────────────────────────────────────────────┐
│ 3. Active Communication                                          │
└─────────────────────────────────────────────────────────────────┘
    session.initialize()
    └─> write_stream(handshake) ──────────────────► Server
    └─> read_stream() ◄──────────────────────────── Server
    
    session.list_tools()
    └─> write_stream(list_request) ─────────────► Server
    └─> read_stream() ◄───────────────────────── Server
    
    session.call_tool()
    └─> write_stream(tool_call) ─────────────────► Server
    └─> read_stream() ◄────────────────────────── Server


┌─────────────────────────────────────────────────────────────────┐
│ 4. Cleanup                                                       │
└─────────────────────────────────────────────────────────────────┘
    Context managers exit
    └─> ClientSession.__aexit__() called
    └─> streamable_http_client.__aexit__() called
    └─> Cleanup callback runs (closes HTTP connection)
```

---

## Key Concepts

### 1. Async Streams

Streams are **async iterators/generators**. They use `async/await` because:

- Network I/O is slow
- Don't want to block while waiting
- Can handle multiple concurrent operations

```python
# Async generator (read stream):
async def read():
    async for chunk in http_response:
        yield chunk

# Async function (write stream):
async def write(data):
    await http_client.post(url, data=data)
```

### 2. Context Managers

Both `streamable_http_client` and `ClientSession` are context managers:

```python
async with streamable_http_client(url) as (read, write, _):
    async with ClientSession(read, write) as session:
        # Use session here
        # Streams are automatically closed when exiting
```

**Why?** Ensures cleanup:
- Close HTTP connections
- Flush buffers
- Release resources

### 3. Bidirectional Communication

MCP is **request/response** pattern:

```
Client              Server
  │                    │
  │─── Request ───────►│
  │                    │
  │◄── Response ───────│
  │                    │
```

Each pair of write/read is one round-trip.

---

## Real-World Analogy

Think of streams like a **phone conversation**:

```
Write Stream = You speaking
Read Stream  = You listening

When you call session.initialize():
    1. You speak: "Hello, I'm client X with capabilities Y"
    2. You listen: "Hi, I'm server Z with capabilities W"
    3. Conversation continues...
```

The **transport** (HTTP) is like the phone line - it carries your voice but doesn't care what you're saying.

---

## Summary

**Read/Write Streams** are the communication layer in MCP:

1. **Created** by `streamable_http_client()` when connecting
2. **Used** by `ClientSession` to send/receive messages
3. **Abstract** away raw HTTP details
4. **Provide** a simple async interface for bidirectional communication

**The pattern**:
```
Your Code → ClientSession → Streams → HTTP → Server
           (high-level)   (transport)  (network)
```

You work with `session.initialize()`, `session.list_tools()`, etc., while the streams handle the messy details of HTTP communication behind the scenes.
