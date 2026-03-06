from tools.tickets import (
    search_tickets_tool, search_tickets,
    create_ticket_tool, create_ticket,
    update_ticket_status_tool, update_ticket_status,
    list_open_tickets_tool, list_open_tickets,
    add_comment_tool, add_comment,
)
from tools.users import get_user_profile_tool, get_user_profile

# Registry mapping tool name -> {"tool": types.Tool, "handler": callable}
# To add a new tool: create its descriptor + handler in the appropriate file,
# then add one entry here. server.py and client.py need zero changes.
tools = {
    search_tickets_tool.name:       {"tool": search_tickets_tool,       "handler": search_tickets},
    create_ticket_tool.name:        {"tool": create_ticket_tool,        "handler": create_ticket},
    update_ticket_status_tool.name: {"tool": update_ticket_status_tool, "handler": update_ticket_status},
    list_open_tickets_tool.name:    {"tool": list_open_tickets_tool,    "handler": list_open_tickets},
    add_comment_tool.name:          {"tool": add_comment_tool,          "handler": add_comment},
    get_user_profile_tool.name:     {"tool": get_user_profile_tool,     "handler": get_user_profile},
}
