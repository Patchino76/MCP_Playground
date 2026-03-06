# How client_v2.py Works

## Overview

`client_v2.py` is an **LLM-driven MCP client** that adds an AI layer on top of the MCP session from `client_v1.py`. Instead of you deciding which tool to call, the LLM (Groq) reads the user's message, decides which tool(s) to call, executes them on the MCP server, and then turns the raw results into a natural language answer.

This is the standard **agentic tool-use loop** used by real MCP clients like Claude Desktop, Cursor, and other AI-powered applications.

Think of it like this: Instead of using tools yourself, you have an AI assistant that uses tools for you.

---

## The Big Picture

```
┌─────────────────┐         Tools         ┌─────────────────┐
│   User Message  │◄─────────────────────►│   LLM (Groq)    │
│                 │   (get_customer,      │                 │
│                 │    get_orders)       │                 │
└─────────────────┘                       └─────────────────┘
        │                                          │
        │  1. User asks question                   │
        │  2. LLM decides which tool to use         │
        │  3. LLM requests tool call                │
        │  4. Client executes tool on MCP server    │
        │  5. Results returned to LLM               │
        │  6. LLM generates natural language answer │
        └──────────────────────────────────────────┘
```

**Key Idea**: The LLM acts as an intelligent intermediary between the user and the MCP tools. It understands natural language, knows which tools to use, and presents results in a conversational format.

---

## Architecture Breakdown

### The Four-Component Stack

```
┌─────────────────────────────────────────────────────────────┐
│                     User Message                            │
│  - Natural language question                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM (Groq)                               │
│  - Understands user intent                                   │
│  - Decides which tools to call                              │
│  - Generates natural language answers                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ClientSession                              │
│  - Executes tools on MCP server                             │
│  - Returns structured results                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server                                │
│  - Provides tools                                            │
│  - Executes tool logic                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Execution Flow

### The Agentic Tool-Use Loop

For each user message, the client runs this loop:

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Collect Tools                                           │
└─────────────────────────────────────────────────────────────────┘
    1. Call session.list_tools()
    2. Convert each MCP Tool to Groq format
    3. Store for use in conversation


┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Send User Message to LLM                                │
└─────────────────────────────────────────────────────────────────┘
    messages = [{"role": "user", "content": user_message}]
    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        tools=groq_tools,
        tool_choice="auto"
    )


┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Check LLM Response                                      │
└─────────────────────────────────────────────────────────────────┘
    if assistant_message.tool_calls:
        → Go to Step 4 (Execute Tools)
    else:
        → Go to Step 6 (Return Answer)


┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Execute Tool Calls                                      │
└─────────────────────────────────────────────────────────────────┘
    For each tool_call:
        1. Extract tool name and arguments
        2. Call session.call_tool(name, arguments)
        3. Get result as string
        4. Append result to messages with role="tool"


┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Loop Back to LLM                                        │
└─────────────────────────────────────────────────────────────────┘
    Send updated messages (with tool results) back to LLM
    → Go back to Step 3


┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Return Final Answer                                     │
└─────────────────────────────────────────────────────────────────┘
    LLM produces natural language answer
    Return to user
```

---

## Detailed Component Analysis

### 1. Tool Format Conversion

```python
def mcp_tool_to_groq(tool: mcp_types.Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        },
    }
```

**What it does**: Converts MCP tool definitions to Groq's expected format.

**Why it's needed**: Different AI providers use different tool formats. Groq (like OpenAI) expects:
```json
{
    "type": "function",
    "function": {
        "name": "get_customer",
        "description": "...",
        "parameters": { <JSON Schema> }
    }
}
```

MCP already provides `inputSchema` as a valid JSON Schema, so we pass it directly.

---

### 2. Tool Execution

```python
async def execute_tool_call(session: ClientSession, tool_name: str, tool_args: dict) -> str:
    result = await session.call_tool(name=tool_name, arguments=tool_args)
    
    if result.isError:
        error_text = result.content[0].text
        return f"Error: {error_text}"
    
    content_text = result.content[0].text
    return content_text
```

**What it does**: Executes a tool on the MCP server and returns the result as a string.

**Key points**:
- Calls the same `session.call_tool()` from `client_v1.py`
- Returns a string (not a structured object) because the LLM needs text
- Handles errors gracefully so the LLM can explain them to the user

---

### 3. The Agentic Loop

```python
async def chat(session: ClientSession, groq_client: AsyncGroq, groq_tools: list[dict], user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]
    
    while True:
        # Ask LLM
        response = await groq_client.chat.completions.create(...)
        assistant_message = response.choices[0].message
        
        # Check if LLM wants to call a tool
        if not assistant_message.tool_calls:
            return assistant_message.content  # Final answer
        
        # Execute tool calls
        messages.append(assistant_message)
        for tool_call in assistant_message.tool_calls:
            tool_result = await execute_tool_call(...)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })
        
        # Loop back with updated conversation
```

**How it works**:

1. **Start**: Create conversation with user message
2. **Ask LLM**: Send conversation + tools to LLM
3. **Check response**:
   - If no tool call → return final answer
   - If tool call → execute it
4. **Execute**: Call tool on MCP server
5. **Append**: Add tool result to conversation
6. **Loop**: Send updated conversation back to LLM
7. **Repeat**: Until LLM gives final answer

**Why the loop?**: The LLM might need to call multiple tools in sequence (multi-step reasoning). For example:
- Call `get_customer` to get customer info
- Call `get_orders` to get their orders
- Then synthesize both into a comprehensive answer

---

### 4. Conversation History Management

The conversation is a list of messages that grows:

```python
messages = [
    {"role": "user", "content": "Who is customer 102?"},
    {"role": "assistant", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "{...}"},
    {"role": "assistant", "content": "Customer 102 is..."}
]
```

**Message roles**:
- `user`: The user's question
- `assistant`: The LLM's response (may include `tool_calls`)
- `tool`: The result of executing a tool

**Why this matters**: The LLM needs full conversation history to:
- Understand context
- Know which tools were called
- See the results of those calls
- Generate a coherent final answer

---

## Complete Execution Example

Let's trace a full conversation:

```
User: "Who is customer 102?"

Step 1: Send to LLM
    messages = [{"role": "user", "content": "Who is customer 102?"}]
    tools = [get_customer, get_orders]
    
Step 2: LLM decides to call tool
    assistant_message = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call_123",
            "function": {
                "name": "get_customer",
                "arguments": '{"customer_id": 102}'
            }
        }]
    }
    
Step 3: Execute tool on MCP server
    result = await session.call_tool("get_customer", {"customer_id": 102})
    tool_result = '{"id": 102, "name": "Bob Smith", ...}'
    
Step 4: Append tool result
    messages.append(assistant_message)
    messages.append({
        "role": "tool",
        "tool_call_id": "call_123",
        "content": '{"id": 102, "name": "Bob Smith", ...}'
    })
    
Step 5: Send back to LLM
    response = await groq_client.chat.completions.create(
        messages=messages,
        tools=tools
    )
    
Step 6: LLM generates final answer
    assistant_message = {
        "role": "assistant",
        "content": "Customer 102 is Bob Smith, located in..."
    }
    
Step 7: Return to user
    "Customer 102 is Bob Smith, located in..."
```

---

## Key MCP Concepts Explained

### 1. Agentic Tool-Use Loop

**What it is**: A pattern where an LLM autonomously decides which tools to call and in what order.

**Why it matters**: This is how real AI assistants work. They don't just answer questions—they can take actions by calling tools.

**Example**: User asks "What should I order for dinner?" → LLM calls weather API, calls restaurant API, calls your preferences, then recommends.

### 2. Tool Choice

```python
tool_choice="auto"  # LLM decides whether to use a tool
```

**What it means**: The LLM can choose to:
- Call a tool (if it needs information)
- Answer directly (if it knows the answer)
- Do both (call tool then explain)

**Other options**:
- `tool_choice="required"`: Must call a tool
- `tool_choice={"type": "function", "function": {"name": "get_customer"}}`: Force specific tool

### 3. Tool Call ID

```python
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": tool_result,
})
```

**What it is**: A unique identifier linking a tool result back to the specific tool call.

**Why it matters**: When the LLM makes multiple tool calls, it needs to know which result belongs to which call.

### 4. JSON Schema in Parameters

```python
"parameters": tool.inputSchema  # Already a valid JSON Schema
```

**What it means**: The MCP tool's `inputSchema` is a JSON Schema describing the expected arguments.

**Why it's useful**: The LLM uses this to understand what arguments to provide and in what format.

---

## Comparison: client_v1 vs client_v2

| Aspect | client_v1 | client_v2 |
|--------|-----------|-----------|
| **Who decides tools?** | You (hardcoded) | LLM (dynamic) |
| **User input** | Function calls | Natural language |
| **Output format** | Raw JSON | Natural language |
| **Complexity** | Simple, predictable | More complex, flexible |
| **Use case** | Programmatic access | Conversational AI |
| **Tool calls** | Explicit | Automatic |

---

## Why Add an LLM?

### Benefits

1. **Natural Language Interface**: Users don't need to know tool names or arguments
2. **Intelligent Tool Selection**: LLM figures out which tools to use
3. **Multi-Step Reasoning**: Can chain multiple tool calls
4. **Contextual Answers**: Synthesizes results into coherent responses
5. **Flexible**: Can handle unanticipated questions

### Trade-offs

1. **Complexity**: More moving parts (LLM API, conversation management)
2. **Cost**: LLM API calls cost money
3. **Latency**: Slower than direct tool calls
4. **Non-deterministic**: Same question may get different answers

---

## Setup Requirements

### 1. Groq API Key

Create a `.env` file in `ch06/`:
```
GROQ_API_KEY=your_key_here
```

Get a free key at https://console.groq.com

### 2. Dependencies

```python
from groq import AsyncGroq
from dotenv import load_dotenv
```

Install with:
```bash
pip install groq python-dotenv
```

---

## Real-World Applications

This pattern is used by:

- **Claude Desktop**: Uses tools to browse files, run commands, etc.
- **Cursor**: AI code editor that uses tools for code analysis
- **ChatGPT Plugins**: Tools that extend AI capabilities
- **Custom AI Agents**: Any application that needs AI to take actions

---

## Summary

`client_v2.py` demonstrates the **agentic tool-use loop**:

```
1. Connect → streamable_http_client() + ClientSession
2. Discover → session.list_tools() + convert to LLM format
3. Chat Loop:
   a. Send user message to LLM
   b. LLM decides whether to call tools
   c. If yes → execute tools, append results, loop back
   d. If no → return final answer
4. Present → Natural language response to user
```

**The key insight**: The LLM acts as an intelligent intermediary that bridges natural language and tool execution. This is the foundation of modern AI assistants that can actually *do* things, not just answer questions.
