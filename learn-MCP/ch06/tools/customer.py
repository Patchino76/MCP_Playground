import json
from schema import Customer
from data import customers
from mcp import types


async def add_customer(arguments: dict) -> list[types.TextContent]:
    """Add a new customer."""
    try:
        input_model = Customer(**arguments)
    except Exception as e:
        raise ValueError(f"Invalid customer data: {e}")

    customers.append(input_model)
    print(f"Customer {input_model.name} added successfully")
    return [types.TextContent(type="text", text=f"Customer {input_model.name} added successfully")]


add_customer_input_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "description": "Customer ID"},
        "name": {"type": "string", "description": "Customer name"},
        "email": {"type": "string", "description": "Customer email"},
    },
    "required": ["id", "name", "email"]
}

add_customer_tool = types.Tool(
    name="add_customer",
    description="Add a new customer",
    inputSchema=add_customer_input_schema,
)


async def get_customer(arguments: dict) -> list[types.TextContent]:
    """Retrieve a customer by their ID."""
    customer_id = arguments.get("customer_id")
    if customer_id is None:
        raise ValueError("customer_id is required")

    match = next((c for c in customers if c.id == customer_id), None)
    if match is None:
        raise ValueError(f"No customer found with id: {customer_id}")

    result = {
        "id": match.id,
        "name": match.name,
        "email": match.email,
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


get_customer_input_schema = {
    "type": "object",
    "properties": {
        "customer_id": {
            "type": "integer",
            "description": "The ID of the customer to retrieve"
        }
    },
    "required": ["customer_id"]
}

get_customer_tool = types.Tool(
    name="get_customer",
    description="Retrieve a customer's details by their customer ID",
    inputSchema=get_customer_input_schema,
)