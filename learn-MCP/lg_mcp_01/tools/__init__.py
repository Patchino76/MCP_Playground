from tools.tickets import search_tickets_tool, search_tickets, create_ticket_tool, create_ticket
from tools.users import get_user_profile_tool, get_user_profile

# Registry mapping tool name -> {"tool": types.Tool, "handler": callable}
tools = {
    search_tickets_tool.name: {"tool": search_tickets_tool, "handler": search_tickets},
    create_ticket_tool.name:  {"tool": create_ticket_tool,  "handler": create_ticket},
    get_user_profile_tool.name: {"tool": get_user_profile_tool, "handler": get_user_profile},
}
