import json
from data import orders, customers
from mcp import types


async def get_orders(arguments: dict) -> list[types.TextContent]:
    """Return all orders for a given customer ID."""
    customer_id = arguments.get("customer_id")
    if customer_id is None:
        raise ValueError("customer_id is required")

    if not any(c.id == customer_id for c in customers):
        raise ValueError(f"No customer found with id: {customer_id}")

    filtered = [o for o in orders if o.customer_id == customer_id]

    result = {
        "customer_id": customer_id,
        "order_count": len(filtered),
        "orders": [
            {
                "id": str(order.id),
                "customer_id": order.customer_id,
                "description": order.description,
            }
            for order in filtered
        ]
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


order_input_schema = {
    "type": "object",
    "properties": {
        "customer_id": {
            "type": "integer",
            "description": "The ID of the customer whose orders to retrieve"
        }
    },
    "required": ["customer_id"]
}

get_orders_tool = types.Tool(
    name="get_orders",
    description="Retrieve all orders for a specific customer by their customer ID",
    inputSchema=order_input_schema,
)
