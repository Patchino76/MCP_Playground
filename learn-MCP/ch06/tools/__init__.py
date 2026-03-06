from tools.orders import get_orders_tool, get_orders
from tools.customer import add_customer_tool, add_customer, get_customer_tool, get_customer

# Registry mapping tool name -> {"tool": types.Tool, "handler": callable}
tools = {
    get_orders_tool.name: {"tool": get_orders_tool, "handler": get_orders},
    add_customer_tool.name: {"tool": add_customer_tool, "handler": add_customer},
    get_customer_tool.name: {"tool": get_customer_tool, "handler": get_customer},
}
