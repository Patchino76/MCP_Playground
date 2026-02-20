"""
tools/tickets.py — MCP tools for ticket operations
====================================================
Two tools live here:
  - search_tickets  : keyword search over open tickets
  - create_ticket   : file a new ticket and return its ID

Each tool follows the exact same pattern as ch06:
  1. A plain dict  → inputSchema  (JSON Schema)
  2. A types.Tool  → the MCP tool descriptor
  3. An async def  → the handler that does the actual work
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import types
from data import tickets
from schema import Ticket


# ── search_tickets ────────────────────────────────────────────────────────────

search_tickets_input_schema = {
    "type": "object",
    "properties": {
        "keyword": {
            "type": "string",
            "description": "Word or phrase to search for in ticket titles and descriptions",
        }
    },
    "required": ["keyword"],
}

search_tickets_tool = types.Tool(
    name="search_tickets",
    description="Search open support tickets by keyword. Returns matching tickets with their ID, title, priority and status.",
    inputSchema=search_tickets_input_schema,
)


async def search_tickets(arguments: dict) -> list[types.TextContent]:
    keyword = arguments.get("keyword", "").lower()
    if not keyword:
        raise ValueError("keyword is required")

    matches = [
        t for t in tickets
        if keyword in t.title.lower() or keyword in t.description.lower()
    ]

    result = {
        "keyword": keyword,
        "match_count": len(matches),
        "tickets": [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "user_email": t.user_email,
            }
            for t in matches
        ],
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ── create_ticket ─────────────────────────────────────────────────────────────

create_ticket_input_schema = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Short title summarising the issue",
        },
        "description": {
            "type": "string",
            "description": "Full description of the problem",
        },
        "user_email": {
            "type": "string",
            "description": "Email address of the user reporting the issue",
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Ticket priority: low, medium, or high",
        },
    },
    "required": ["title", "description", "user_email", "priority"],
}

create_ticket_tool = types.Tool(
    name="create_ticket",
    description="Create a new IT support ticket. Returns the new ticket ID and creation timestamp.",
    inputSchema=create_ticket_input_schema,
)


async def create_ticket(arguments: dict) -> list[types.TextContent]:
    try:
        ticket = Ticket(**arguments)
    except Exception as e:
        raise ValueError(f"Invalid ticket data: {e}")

    tickets.append(ticket)

    result = {
        "id": ticket.id,
        "title": ticket.title,
        "priority": ticket.priority,
        "status": ticket.status,
        "user_email": ticket.user_email,
        "created_at": ticket.created_at,
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
