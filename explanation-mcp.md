# Low-Level MCP Server Implementation - Detailed Explanation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [File-by-File Analysis](#file-by-file-analysis)
4. [Key Concepts](#key-concepts)
5. [Request Flow](#request-flow)
6. [Data Models](#data-models)
7. [Tool Implementation](#tool-implementation)

---

## Overview

This is a **Model Context Protocol (MCP)** server implementation using the **low-level API** from the `mcp` Python library. The server provides a marketing/e-commerce domain API with tools for managing customers and orders. It uses HTTP transport via Starlette and Uvicorn.

**Key Characteristics:**
- **Low-level MCP API**: Direct control over server lifecycle and tool handlers
- **HTTP Transport**: Uses StreamableHTTPSessionManager for web-based communication
- **Tool-based Architecture**: Exposes functionality as callable tools with JSON schemas
- **In-memory Data**: Uses Python lists for data storage (not persistent)

---

## Architecture

```
ch06/
├── server.py          # Main server entry point and HTTP setup
├── schema.py          # Pydantic data models
├── data.py            # In-memory data storage
├── tools/             # Tool implementations
│   ├── __init__.py    # Tool registry
│   ├── customer.py    # Customer management tool
│   └── orders.py      # Order retrieval tool
└── __init__.py        # Empty package marker
```

**Component Relationships:**
```
server.py (HTTP Server)
    ↓
StreamableHTTPSessionManager (MCP Protocol Handler)
    ↓
Server (MCP Low-level Server)
    ↓
Tool Registry (tools/__init__.py)
    ↓
Tool Handlers (customer.py, orders.py)
    ↓
Data Layer (data.py + schema.py)
```

---

## File-by-File Analysis

### 1. `server.py` - Main Server Entry Point

**Purpose:** Initializes the MCP server, sets up HTTP transport, and defines tool endpoints.

#### Key Components:

**Server Initialization (Lines 21-33):**
```python
@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    print("Server starting...")
    try:
        yield {"status": "ready"}
    finally:
        print("cleanup")

server = Server("marketing-server", lifespan=server_lifespan)
```

- **`server_lifespan`**: Async context manager for server lifecycle management
- **`yield {"status": "ready"}`**: Provides context to the server during operation
- **`Server` class**: Core MCP server instance with name and lifespan handler

**Tool List Handler (Lines 36-41):**
```python
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tool_list = []
    for entry in tools.values():
        tool_list.append(entry["tool"])
    return tool_list
```

- **Decorator**: `@server.list_tools()` registers this as the handler for tool listing requests
- **Returns**: List of `types.Tool` objects describing available tools
- **Iterates**: Through the tool registry to collect all tool definitions

**Tool Call Handler (Lines 44-49):**
```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name not in tools:
        raise ValueError(f"Unknown tool: {name}")
    handler = tools[name]["handler"]
    return await handler(arguments)
```

- **Decorator**: `@server.call_tool()` registers this as the handler for tool execution
- **Parameters**:
  - `name`: Tool identifier (e.g., "add_customer")
  - `arguments`: Dictionary of validated arguments from the client
- **Dispatch**: Looks up the handler in the tool registry and executes it
- **Returns**: List of `TextContent` objects (MCP protocol response format)

**HTTP Transport Setup (Lines 52-68):**
```python
session_manager = StreamableHTTPSessionManager(server)

@asynccontextmanager
async def app_lifespan(app: Starlette):
    async with session_manager.run():
        print("Server is running on http://localhost:8000/mcp")
        yield

app = Starlette(
    routes=[
        Mount("/mcp", app=session_manager.handle_request),
    ],
    lifespan=app_lifespan,
)
```

- **`StreamableHTTPSessionManager`**: Bridges MCP protocol with HTTP transport
- **`session_manager.run()`**: Starts the MCP session manager
- **`Mount("/mcp", ...)`**: Exposes MCP endpoint at `/mcp` path
- **`app_lifespan`**: Manages the Starlette application lifecycle

**Server Entry (Lines 71-72):**
```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- **Uvicorn**: ASGI server that runs the Starlette application
- **Host**: `0.0.0.0` listens on all network interfaces
- **Port**: 8000 for HTTP connections

---

### 2. `schema.py` - Pydantic Data Models

**Purpose:** Defines the data structure schemas using Pydantic for validation and serialization.

#### Models Defined:

**Customer (Lines 4-7):**
```python
class Customer(BaseModel):
    id: int
    name: str
    email: str
```

- **Purpose**: Represents a customer entity
- **Fields**:
  - `id`: Integer identifier
  - `name`: Customer's full name
  - `email`: Contact email address

**Category (Lines 10-13):**
```python
class Category(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str
```

- **Purpose**: Represents product categories
- **Auto-generated ID**: Uses `uuid.uuid4()` default factory
- **Fields**: `name` and `description` for category metadata

**Product (Lines 16-20):**
```python
class Product(BaseModel):
    id: int
    name: str
    price: float
    description: str
```

- **Purpose**: Represents products in the catalog
- **Fields**: `id`, `name`, `price` (float), and `description`

**CartItem (Lines 23-27):**
```python
class CartItem(BaseModel):
    id: int
    cart_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: int
    quantity: int
```

- **Purpose**: Represents items in a shopping cart
- **Relationship**: Links to a cart via `cart_id` and product via `product_id`
- **Quantity**: Number of units of the product

**Cart (Lines 30-32):**
```python
class Cart(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    customer_id: int
```

- **Purpose**: Represents a shopping cart for a customer
- **Relationship**: Links to customer via `customer_id`

**Order (Lines 35-38):**
```python
class Order(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    customer_id: int
    description: str
```

- **Purpose**: Represents customer orders
- **Relationship**: Links to customer via `customer_id`
- **Auto-generated ID**: Uses UUID for unique order identifiers

**Pydantic Benefits:**
- Automatic validation of input data
- JSON serialization/deserialization
- Type hints for IDE support
- Default value generation

---

### 3. `data.py` - In-Memory Data Storage

**Purpose:** Provides mock data for testing and demonstration purposes.

#### Data Collections:

**Products (Lines 4-8):**
```python
products = [
    Product(id=1, name="Product 1", price=10.0, description="Description of Product 1"),
    Product(id=2, name="Product 2", price=20.0, description="Description of Product 2"),
    Product(id=3, name="Product 3", price=30.0, description="Description of Product 3"),
]
```

- Three sample products with incremental IDs and prices

**Orders (Lines 10-14):**
```python
orders = [
    Order(id=uuid.uuid4(), customer_id=101, description="Order 1 for customer 101"),
    Order(id=uuid.uuid4(), customer_id=101, description="Order 2 for customer 101"),
    Order(id=uuid.uuid4(), customer_id=102, description="Order 1 for customer 102"),
]
```

- Three orders: two for customer 101, one for customer 102
- Uses UUIDs for unique order identifiers

**Customers (Lines 16-18):**
```python
customers = [
    Customer(id=1, name="Customer 1", email="email"),
]
```

- Single sample customer (id=1)

**Categories (Lines 20-24):**
```python
categories = [
    Category(id=uuid.uuid4(), name="Category 1", description="Description of Category 1"),
    Category(id=uuid.uuid4(), name="Category 2", description="Description of Category 2"),
    Category(id=uuid.uuid4(), name="Category 3", description="Description of Category 3"),
]
```

- Three sample categories with UUID identifiers

**Empty Collections (Lines 26-27):**
```python
carts = []
cart_items = []
```

- Empty lists for cart and cart items (not currently used)

**Note:** Data is stored in memory and will be lost when the server restarts. For production, use a database.

---

### 4. `tools/__init__.py` - Tool Registry

**Purpose:** Central registry that maps tool names to their definitions and handlers.

#### Registry Structure (Lines 4-8):
```python
tools = {
    get_orders_tool.name: {"tool": get_orders_tool, "handler": get_orders},
    add_customer_tool.name: {"tool": add_customer_tool, "handler": add_customer},
}
```

**Dictionary Structure:**
- **Key**: Tool name (e.g., "get_orders")
- **Value**: Dictionary with two entries:
  - `"tool"`: `types.Tool` object (metadata: name, description, inputSchema)
  - `"handler"`: Async callable function (executes the tool logic)

**Pattern:**
```python
tools = {
    "tool_name": {
        "tool": types.Tool(...),           # Tool definition
        "handler": async_function,          # Tool implementation
    }
}
```

**Benefits:**
- Centralized tool registration
- Easy to add new tools
- Clean separation between definition and implementation
- Supports dynamic tool discovery

---

### 5. `tools/customer.py` - Customer Management Tool

**Purpose:** Implements the `add_customer` tool for creating new customers.

#### Handler Function (Lines 6-15):
```python
async def add_customer(arguments: dict) -> list[types.TextContent]:
    """Add a new customer."""
    try:
        input_model = Customer(**arguments)
    except Exception as e:
        raise ValueError(f"Invalid customer data: {e}")

    customers.append(input_model)
    print(f"Customer {input_model.name} added successfully")
    return [types.TextContent(type="text", text=f"Customer {input_model.name} added successfully")]
```

**Execution Flow:**
1. **Validation**: Creates `Customer` model from arguments (Pydantic validates)
2. **Error Handling**: Catches validation errors and raises `ValueError`
3. **Storage**: Appends validated customer to `customers` list
4. **Logging**: Prints success message to console
5. **Response**: Returns `TextContent` with success message

**Input Schema (Lines 18-26):
```python
add_customer_input_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "description": "Customer ID"},
        "name": {"type": "string", "description": "Customer name"},
        "email": {"type": "string", "description": "Customer email"},
    },
    "required": ["id", "name", "email"]
}
```

- **JSON Schema**: Defines expected input structure
- **Properties**: Three fields with types and descriptions
- **Required**: All fields are mandatory

**Tool Definition (Lines 28-32):
```python
add_customer_tool = types.Tool(
    name="add_customer",
    description="Add a new customer",
    inputSchema=add_customer_input_schema,
)
```

- **`types.Tool`**: MCP protocol tool definition
- **Fields**:
  - `name`: Unique identifier for the tool
  - `description`: Human-readable description
  - `inputSchema`: JSON schema for validation

---

### 6. `tools/orders.py` - Order Retrieval Tool

**Purpose:** Implements the `get_orders` tool for querying orders.

#### Handler Function (Lines 6-28):
```python
async def get_orders(arguments: dict) -> list[types.TextContent]:
    """Return all orders, optionally filtered by customer ID."""
    customer_id = arguments.get("customer_id", 0)

    if customer_id != 0 and not any(c.id == customer_id for c in customers):
        raise ValueError(f"Invalid customer_id: {customer_id}")

    filtered = (
        [o for o in orders if o.customer_id == customer_id]
        if customer_id != 0 else
        orders
    )

    result = {
        "orders": [
            {
                "id": str(order.id),
                "customer_id": order.customer_id
            }
            for order in filtered
        ]
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
```

**Execution Flow:**
1. **Parameter Extraction**: Gets `customer_id` from arguments (defaults to 0)
2. **Validation**: Checks if customer exists (when filtering)
3. **Filtering**: 
   - If `customer_id != 0`: Filters orders by customer
   - Otherwise: Returns all orders
4. **Serialization**: Converts to JSON-serializable format
5. **Response**: Returns `TextContent` with JSON string

**Input Schema (Lines 31-40):
```python
order_input_schema = {
    "type": "object",
    "properties": {
        "customer_id": {
            "type": "integer",
            "description": "Filter orders by customer ID (0 for all orders)"
        }
    },
    "required": []
}
```

- **Optional Parameter**: `customer_id` is not required
- **Default Behavior**: `0` means "get all orders"

**Tool Definition (Lines 42-46):
```python
get_orders_tool = types.Tool(
    name="get_orders",
    description="Retrieve orders, optionally filtered by customer ID",
    inputSchema=order_input_schema,
)
```

---

## Key Concepts

### 1. Model Context Protocol (MCP)

**Definition:** MCP is a protocol for AI assistants to interact with external systems through tools.

**Core Concepts:**
- **Tools**: Callable functions that perform specific operations
- **Resources**: Data sources (not used in this implementation)
- **Prompts**: Reusable prompt templates (not used here)
- **Transport**: Communication mechanism (HTTP, stdio, etc.)

**Protocol Flow:**
1. Client requests tool list → Server returns available tools
2. Client calls tool with arguments → Server validates and executes
3. Server returns results → Client processes response

### 2. Low-Level vs High-Level MCP API

**Low-Level API (used here):**
- Direct control over server lifecycle
- Manual tool registration and handler mapping
- Explicit request/response handling
- More flexible, requires more boilerplate

**High-Level API:**
- Decorators for automatic registration
- Built-in validation and serialization
- Less code, less control
- Simpler for common use cases

**This implementation uses low-level API** for maximum control and educational purposes.

### 3. Async/Await Pattern

**Purpose:** Handles concurrent I/O operations without blocking.

**Used in:**
- Server lifespan management
- Tool handler execution
- HTTP session management
- Database-like operations

**Benefits:**
- Non-blocking I/O
- Better resource utilization
- Scalable for multiple clients

### 4. Context Managers

**Definition:** Python pattern for resource management (`with` statement).

**Two Types Used:**

**1. `@asynccontextmanager` (server_lifespan):**
```python
@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    print("Server starting...")
    try:
        yield {"status": "ready"}
    finally:
        print("cleanup")
```

- **Setup**: Runs before `yield`
- **Context**: Returns data during operation
- **Cleanup**: Runs in `finally` block

**2. `app_lifespan` (Starlette):**
```python
@asynccontextmanager
async def app_lifespan(app: Starlette):
    async with session_manager.run():
        print("Server is running on http://localhost:8000/mcp")
        yield
```

- **Nested**: Manages both app and session lifecycle
- **Session Manager**: Handles MCP protocol sessions

### 5. JSON Schema Validation

**Purpose:** Defines and validates tool input structure.

**Schema Components:**
- `type`: Data type (object, string, integer, etc.)
- `properties`: Field definitions
- `required`: List of mandatory fields
- `description`: Human-readable field descriptions

**Example:**
```python
{
    "type": "object",
    "properties": {
        "id": {"type": "integer", "description": "Customer ID"},
        "name": {"type": "string", "description": "Customer name"},
    },
    "required": ["id", "name"]
}
```

### 6. Pydantic Models

**Purpose:** Data validation and serialization using Python type hints.

**Key Features:**
- Automatic validation
- Type coercion
- JSON serialization
- Default values
- Field descriptions

**Usage Pattern:**
```python
class Customer(BaseModel):
    id: int
    name: str
    email: str

# Validation happens automatically
customer = Customer(**arguments)  # Raises ValidationError if invalid
```

### 7. Starlette & Uvicorn

**Starlette:** Lightweight ASGI framework for building web applications.

**Features Used:**
- **Routes**: URL routing with `Mount`
- **Lifespan**: Application lifecycle management
- **ASGI**: Asynchronous Server Gateway Interface

**Uvicorn:** ASGI server that runs Starlette applications.

**Configuration:**
- **Host**: `0.0.0.0` (all interfaces)
- **Port**: `8000`
- **Protocol**: HTTP

### 8. StreamableHTTPSessionManager

**Purpose:** Bridges MCP protocol with HTTP transport.

**Responsibilities:**
- Manages MCP sessions over HTTP
- Handles request/response translation
- Maintains session state
- Exposes `handle_request` for HTTP endpoint

**Integration:**
```python
session_manager = StreamableHTTPSessionManager(server)
app = Starlette(
    routes=[
        Mount("/mcp", app=session_manager.handle_request),
    ],
    ...
)
```

---

## Request Flow

### Tool Listing Flow

```
Client HTTP Request
    ↓
GET /mcp
    ↓
Starlette Router
    ↓
session_manager.handle_request
    ↓
StreamableHTTPSessionManager
    ↓
MCP Protocol Handler
    ↓
server.list_tools() → handle_list_tools()
    ↓
Tool Registry (tools/__init__.py)
    ↓
Return types.Tool objects
    ↓
JSON Response to Client
```

### Tool Execution Flow

```
Client HTTP Request (POST with tool name and arguments)
    ↓
POST /mcp
    ↓
Starlette Router
    ↓
session_manager.handle_request
    ↓
StreamableHTTPSessionManager
    ↓
MCP Protocol Handler
    ↓
server.call_tool() → handle_call_tool(name, arguments)
    ↓
Tool Registry Lookup
    ↓
Execute Handler Function
    ↓
Pydantic Validation (if applicable)
    ↓
Business Logic Execution
    ↓
Data Access (data.py)
    ↓
Return TextContent
    ↓
JSON Response to Client
```

### Example: Adding a Customer

**1. Client Request:**
```json
POST /mcp
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "add_customer",
        "arguments": {
            "id": 2,
            "name": "John Doe",
            "email": "john@example.com"
        }
    },
    "id": 1
}
```

**2. Server Processing:**
```
handle_call_tool("add_customer", {...})
    ↓
tools["add_customer"]["handler"] = add_customer
    ↓
add_customer({"id": 2, "name": "John Doe", "email": "john@example.com"})
    ↓
Customer(**arguments) → Pydantic validation
    ↓
customers.append(customer)
    ↓
Return TextContent("Customer John Doe added successfully")
```

**3. Client Response:**
```json
{
    "jsonrpc": "2.0",
    "result": {
        "content": [
            {
                "type": "text",
                "text": "Customer John Doe added successfully"
            }
        ]
    },
    "id": 1
}
```

---

## Data Models

### Entity Relationships

```
Customer (1) ----< (N) Order
    |
    | (1)
    |
    v
(1) ----< (N) Cart
    |
    | (1)
    |
    v
(N) CartItem ----> (1) Product
                     |
                     | (N)
                     v
                  Category
```

### Data Flow

**1. Customer Creation:**
```
Client → add_customer() → Customer model → customers list
```

**2. Order Retrieval:**
```
Client → get_orders(customer_id) → Filter orders list → JSON response
```

**3. Data Persistence:**
- All data stored in Python lists
- Lost on server restart
- Not thread-safe for concurrent access
- Suitable for testing/demonstration only

---

## Tool Implementation

### Tool Pattern

Every tool follows this pattern:

**1. Handler Function:**
```python
async def tool_name(arguments: dict) -> list[types.TextContent]:
    # 1. Validate inputs
    # 2. Execute business logic
    # 3. Return results
    return [types.TextContent(type="text", text="result")]
```

**2. Input Schema:**
```python
input_schema = {
    "type": "object",
    "properties": {
        "param1": {"type": "string", "description": "..."},
    },
    "required": ["param1"]
}
```

**3. Tool Definition:**
```python
tool = types.Tool(
    name="tool_name",
    description="Tool description",
    inputSchema=input_schema,
)
```

**4. Registry Entry:**
```python
tools = {
    tool.name: {"tool": tool, "handler": tool_name}
}
```

### Adding a New Tool

**Step 1: Create Handler (e.g., `tools/product.py`):**
```python
from schema import Product
from data import products
from mcp import types

async def get_product(arguments: dict) -> list[types.TextContent]:
    product_id = arguments["id"]
    product = next((p for p in products if p.id == product_id), None)
    if not product:
        raise ValueError(f"Product not found: {product_id}")
    return [types.TextContent(type="text", text=product.model_dump_json())]

product_input_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "description": "Product ID"}
    },
    "required": ["id"]
}

get_product_tool = types.Tool(
    name="get_product",
    description="Get a product by ID",
    inputSchema=product_input_schema,
)
```

**Step 2: Register in `tools/__init__.py`:**
```python
from tools.product import get_product_tool, get_product

tools = {
    # ... existing tools
    get_product_tool.name: {"tool": get_product_tool, "handler": get_product},
}
```

**Step 3: Restart server**
The new tool will be automatically available to clients.

---

## Error Handling

### Validation Errors

**Pydantic Validation:**
```python
try:
    input_model = Customer(**arguments)
except Exception as e:
    raise ValueError(f"Invalid customer data: {e}")
```

**Customer Validation in get_orders:**
```python
if customer_id != 0 and not any(c.id == customer_id for c in customers):
    raise ValueError(f"Invalid customer_id: {customer_id}")
```

### Unknown Tool

```python
if name not in tools:
    raise ValueError(f"Unknown tool: {name}")
```

### Error Propagation

Errors are raised as exceptions and caught by the MCP server, which converts them to JSON-RPC error responses.

---

## Testing the Server

### Running the Server

```bash
cd ch06
python server.py
```

Server starts at: `http://localhost:8000/mcp`

### Example Client Requests

**List Tools:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'
```

**Add Customer:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_customer",
      "arguments": {
        "id": 3,
        "name": "Alice Smith",
        "email": "alice@example.com"
      }
    },
    "id": 2
  }'
```

**Get Orders:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_orders",
      "arguments": {
        "customer_id": 101
      }
    },
    "id": 3
  }'
```

---

## Extensions and Improvements

### Potential Enhancements

**1. Database Integration:**
- Replace in-memory lists with SQLAlchemy
- Add database connection pooling
- Implement migrations

**2. Authentication:**
- Add API key authentication
- Implement JWT tokens
- Rate limiting

**3. More Tools:**
- Product management (CRUD)
- Cart operations
- Order processing
- Category management

**4. Error Handling:**
- Custom exception types
- Detailed error messages
- Logging framework integration

**5. Testing:**
- Unit tests for handlers
- Integration tests for HTTP endpoints
- Mock data fixtures

**6. Documentation:**
- OpenAPI/Swagger spec
- Tool usage examples
- API documentation

---

## Summary

This MCP server implementation demonstrates:

1. **Low-level MCP API usage** with manual tool registration
2. **HTTP transport** via Starlette and Uvicorn
3. **Tool-based architecture** with clean separation of concerns
4. **Pydantic models** for data validation
5. **Async/await patterns** for non-blocking operations
6. **Context managers** for resource lifecycle management
7. **JSON schemas** for input validation
8. **Registry pattern** for tool organization

The server provides a solid foundation for building MCP-compliant APIs that can be integrated with AI assistants and other MCP clients.
