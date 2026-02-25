"""
tools/tickets.py — MCP tools for ticket operations
====================================================
Five tools live here:
  - search_tickets        : keyword search over all tickets
  - create_ticket         : file a new ticket and return its ID
  - update_ticket_status  : change a ticket's status (open/in_progress/resolved)
  - list_open_tickets     : return all currently open or in-progress tickets
  - add_comment           : append a timestamped comment to a ticket

Each tool follows the exact same three-part pattern:
  1. A plain dict  → inputSchema  (JSON Schema — what arguments the LLM must provide)
  2. A types.Tool  → the MCP tool descriptor  (name + description + schema)
  3. An async def  → the handler that does the actual work and returns TextContent

This pattern is the LOW-LEVEL MCP API. The high-level API (FastMCP) uses
decorators to hide this structure — here it is fully explicit so you can
see exactly what MCP expects.
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import types
from data import tickets
from schema import Ticket


# ── search_tickets ────────────────────────────────────────────────────────────
# Searches ALL tickets (any status) by keyword in title or description.

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
    description=(
        "Search support tickets by keyword. Scans both title and description. "
        "Returns matching tickets with their ID, title, priority, status, and owner email. "
        "Always call this first to check for duplicates before creating a new ticket."
    ),
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
                "created_at": t.created_at,
            }
            for t in matches
        ],
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ── create_ticket ─────────────────────────────────────────────────────────────
# Creates a new ticket. Pydantic validates all fields before persisting.

create_ticket_input_schema = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Short title summarising the issue (max ~80 chars)",
        },
        "description": {
            "type": "string",
            "description": "Full description of the problem with all relevant details",
        },
        "user_email": {
            "type": "string",
            "description": "Email address of the user reporting the issue",
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Ticket priority based on user SLA: critical/high SLA → high, standard SLA → medium or low",
        },
    },
    "required": ["title", "description", "user_email", "priority"],
}

create_ticket_tool = types.Tool(
    name="create_ticket",
    description=(
        "Create a new IT support ticket. Only call this after search_tickets confirms "
        "no duplicate exists and after get_user_profile confirms the correct priority. "
        "Returns the new ticket ID, priority, status, and creation timestamp."
    ),
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


# ── update_ticket_status ──────────────────────────────────────────────────────
# Changes a ticket's lifecycle status. Critical for the agent to close tickets.

update_ticket_status_input_schema = {
    "type": "object",
    "properties": {
        "ticket_id": {
            "type": "string",
            "description": "The ticket ID to update (e.g. T-AA1B2C)",
        },
        "status": {
            "type": "string",
            "enum": ["open", "in_progress", "resolved"],
            "description": "The new status for the ticket",
        },
    },
    "required": ["ticket_id", "status"],
}

update_ticket_status_tool = types.Tool(
    name="update_ticket_status",
    description=(
        "Update the status of an existing support ticket. "
        "Valid transitions: open → in_progress → resolved. "
        "Returns the updated ticket details. "
        "Use this when a user says their issue is fixed or when escalating."
    ),
    inputSchema=update_ticket_status_input_schema,
)


async def update_ticket_status(arguments: dict) -> list[types.TextContent]:
    ticket_id = arguments.get("ticket_id", "").strip()
    new_status = arguments.get("status", "").strip()

    if not ticket_id:
        raise ValueError("ticket_id is required")
    if not new_status:
        raise ValueError("status is required")

    ticket = next((t for t in tickets if t.id == ticket_id), None)
    if ticket is None:
        result = {"error": f"No ticket found with ID: {ticket_id}"}
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    old_status = ticket.status
    ticket.status = new_status  # type: ignore[assignment]

    result = {
        "id": ticket.id,
        "title": ticket.title,
        "old_status": old_status,
        "new_status": ticket.status,
        "priority": ticket.priority,
        "user_email": ticket.user_email,
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ── list_open_tickets ─────────────────────────────────────────────────────────
# Returns all non-resolved tickets. Useful for status overview queries.

list_open_tickets_input_schema = {
    "type": "object",
    "properties": {
        "priority_filter": {
            "type": "string",
            "enum": ["low", "medium", "high", "all"],
            "description": "Filter by priority. Use 'all' to return every open/in-progress ticket.",
        }
    },
    "required": ["priority_filter"],
}

list_open_tickets_tool = types.Tool(
    name="list_open_tickets",
    description=(
        "List all open or in-progress support tickets, optionally filtered by priority. "
        "Use priority_filter='all' to see every active ticket. "
        "Useful when a user asks 'what tickets are open?' or 'how many high-priority issues exist?'"
    ),
    inputSchema=list_open_tickets_input_schema,
)


async def list_open_tickets(arguments: dict) -> list[types.TextContent]:
    priority_filter = arguments.get("priority_filter", "all").lower()

    active = [t for t in tickets if t.status in ("open", "in_progress")]

    if priority_filter != "all":
        active = [t for t in active if t.priority == priority_filter]

    result = {
        "priority_filter": priority_filter,
        "count": len(active),
        "tickets": [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "user_email": t.user_email,
                "created_at": t.created_at,
            }
            for t in active
        ],
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ── add_comment ───────────────────────────────────────────────────────────────
# Appends a timestamped comment to a ticket. Demonstrates mutable state.

add_comment_input_schema = {
    "type": "object",
    "properties": {
        "ticket_id": {
            "type": "string",
            "description": "The ticket ID to comment on (e.g. T-AA1B2C)",
        },
        "comment": {
            "type": "string",
            "description": "The comment text to append to the ticket",
        },
    },
    "required": ["ticket_id", "comment"],
}

add_comment_tool = types.Tool(
    name="add_comment",
    description=(
        "Add a timestamped comment to an existing support ticket. "
        "Use this to record investigation notes, workarounds, or status updates "
        "on behalf of the support agent."
    ),
    inputSchema=add_comment_input_schema,
)


async def add_comment(arguments: dict) -> list[types.TextContent]:
    ticket_id = arguments.get("ticket_id", "").strip()
    comment_text = arguments.get("comment", "").strip()

    if not ticket_id:
        raise ValueError("ticket_id is required")
    if not comment_text:
        raise ValueError("comment is required")

    ticket = next((t for t in tickets if t.id == ticket_id), None)
    if ticket is None:
        result = {"error": f"No ticket found with ID: {ticket_id}"}
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    timestamp = datetime.now().isoformat(timespec="seconds")
    ticket.comments.append({"timestamp": timestamp, "text": comment_text})

    result = {
        "id": ticket.id,
        "title": ticket.title,
        "comment_added": comment_text,
        "timestamp": timestamp,
        "total_comments": len(ticket.comments),
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
