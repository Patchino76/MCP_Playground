# MCP Client & Streams Knowledge Test

This test covers the material from `streams_explained.md` and `client1.md`. Answer each question by selecting the best option (a, b, c, or d).

---

## Questions

### 1. What is the primary purpose of read and write streams in MCP?

a) To store data locally on the client machine
b) To serve as communication channels between client and server
c) To encrypt messages for security
d) To cache responses for faster access

### 2. Which of the following best describes the write stream?

a) An async iterator that yields incoming data from the server
b) An async function that sends outgoing data to the server
c) A synchronous function for logging purposes
d) A buffer that stores all server responses

### 3. What does `streamable_http_client()` return when called?

a) A single HTTP client object
b) Only a read stream
c) A read stream, write stream, and cleanup callback
d) Just the write stream

### 4. What is the first required step after creating a ClientSession?

a) Call `session.list_tools()`
b) Call `session.initialize()`
c) Call `session.call_tool()`
d) Call `session.close()`

### 5. What happens during the MCP handshake?

a) Client sends capabilities, server responds with its capabilities and info
b) Server authenticates the client's credentials
c) Client downloads all available tools
d) Server initializes its database connection

### 6. What does `session.list_tools()` return?

a) A list of tool names only
b) A ListToolsResult object containing tool definitions with schemas
c) A dictionary with tool names as keys
d) A JSON string of all tools

### 7. What is the purpose of the inputSchema in a tool definition?

a) To encrypt the tool's arguments
b) To describe what arguments the tool accepts and their format
c) To store the tool's execution history
d) To validate the server's response format

### 8. How do you check if a tool call resulted in an error?

a) Check if the response is None
b) Check `result.isError`
c) Try to catch an exception
d) Check if `result.content` is empty

### 9. What does the `content` attribute of a CallToolResult contain?

a) A single string with the result
b) A list of content blocks (TextContent, ImageContent, etc.)
c) The raw HTTP response
d) Only error messages

### 10. What is the correct pattern for calling a tool with arguments?

a) `session.call_tool("get_customer", customer_id=101)`
b) `session.call_tool(name="get_customer", arguments={"customer_id": 101})`
c) `session.call_tool({"name": "get_customer", "customer_id": 101})`
d) `session.call_tool("get_customer", {"customer_id": 101})`

### 11. Why are both `streamable_http_client` and `ClientSession` context managers?

a) To automatically retry failed requests
b) To ensure proper cleanup of resources like closing HTTP connections
c) To enable parallel execution
d) To log all messages automatically

### 12. What is the role of the ClientSession in the MCP architecture?

a) It handles raw HTTP communication
b) It provides a high-level API for MCP protocol methods
c) It stores all tool definitions locally
d) It encrypts all messages

### 13. What communication pattern does MCP use?

a) Publish/subscribe
b) Request/response
c) Event-driven
d) Streaming only

### 14. What does the third value (`_`) returned by `streamable_http_client()` represent?

a) The server's response time
b) A cleanup callback function
c) An error handler
d) The connection timeout value

### 15. In the stream analogy, what does the write stream represent?

a) You listening to the server
b) You speaking to the server
c) The phone line carrying the conversation
d) The server processing your request

### 16. What is the purpose of JSON Schema in tool definitions?

a) To compress the data before transmission
b) To describe the structure and requirements of tool arguments
c) To store tool execution results
d) To authenticate the client

### 17. What happens when you call `session.initialize()`?

a) It downloads all tools from the server
b) It performs the MCP handshake and exchanges capabilities
c) It starts a new HTTP server
d) It clears the session cache

### 18. Why is `client_v1.py` called a "direct" client?

a) Because it uses direct database connections
b) Because it calls tools directly without LLM involvement
c) Because it bypasses the MCP protocol
d) Because it only works with localhost

### 19. What is the transport layer in the MCP architecture?

a) The communication channel (HTTP, stdio, WebSocket)
b) The ClientSession object
c) The tool execution engine
d) The JSON parsing layer

### 20. What type of content does the demo server return in its tool responses?

a) ImageContent only
b) AudioContent only
c) TextContent containing JSON strings
d) Mixed content with text and images

### 21. How does the client handle errors from the server?

a) Errors are thrown as exceptions
b) Errors are returned in the response with `isError: true`
c) Errors are logged automatically
d) Errors are ignored by default

### 22. What is the benefit of separating streams from ClientSession?

a) It makes the code more complex
b) It allows different transports to provide the same interface
c) It forces synchronous operations
d) It reduces performance

### 23. What must you do before calling any other session methods?

a) Call `session.list_tools()`
b) Call `session.initialize()`
c) Create a new HTTP client
d) Set up authentication

### 24. What does the `required` field in a JSON Schema indicate?

a) Which parameters are optional
b) Which parameters must be provided
c) Which parameters have default values
d) Which parameters are deprecated

### 25. In the three-layer stack, what does the transport layer handle?

a) High-level MCP protocol methods
b) HTTP communication and stream management
c) Tool execution logic
d) User interface rendering

---

## Answer Key

| Question | Correct Answer |
|----------|----------------|
| 1        | b              |
| 2        | b              |
| 3        | c              |
| 4        | b              |
| 5        | a              |
| 6        | b              |
| 7        | b              |
| 8        | b              |
| 9        | b              |
| 10       | b              |
| 11       | b              |
| 12       | b              |
| 13       | b              |
| 14       | b              |
| 15       | b              |
| 16       | b              |
| 17       | b              |
| 18       | b              |
| 19       | a              |
| 20       | c              |
| 21       | b              |
| 22       | b              |
| 23       | b              |
| 24       | b              |
| 25       | b              |

---

## Scoring

- **20-25 correct**: Excellent! You have a strong understanding of MCP clients and streams.
- **15-19 correct**: Good! You understand most concepts but may want to review some areas.
- **10-14 correct**: Fair. You have the basics but should review the material more thoroughly.
- **Below 10**: Please review `streams_explained.md` and `client1.md` again before proceeding.
