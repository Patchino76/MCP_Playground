"""
tools/users.py — MCP tool for user profile lookup
===================================================
One tool:
  - get_user_profile : retrieve a user's department, machine, and SLA tier
                       by their email address

The agent calls this before creating a ticket so it can set the right
priority based on the user's SLA tier.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import types
from data import user_profiles


# ── get_user_profile ──────────────────────────────────────────────────────────

get_user_profile_input_schema = {
    "type": "object",
    "properties": {
        "email": {
            "type": "string",
            "description": "The email address of the user to look up",
        }
    },
    "required": ["email"],
}

get_user_profile_tool = types.Tool(
    name="get_user_profile",
    description=(
        "Retrieve a user's profile by their email address. "
        "Returns their name, department, machine type, and SLA tier "
        "(standard / high / critical). Use this to determine ticket priority."
    ),
    inputSchema=get_user_profile_input_schema,
)


async def get_user_profile(arguments: dict) -> list[types.TextContent]:
    email = arguments.get("email", "").strip().lower()
    if not email:
        raise ValueError("email is required")

    match = next((u for u in user_profiles if u.email.lower() == email), None)
    if match is None:
        raise ValueError(f"No user profile found for email: {email}")

    result = {
        "email": match.email,
        "name": match.name,
        "department": match.department,
        "machine": match.machine,
        "sla_tier": match.sla_tier,
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
