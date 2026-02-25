"""
schema.py — Pydantic models for the IT Support Ticket Assistant
===============================================================
These are the domain objects that flow through the system.
Pydantic gives us free validation and easy dict/JSON conversion.
"""

import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    email: str
    name: str
    department: str
    machine: str
    sla_tier: Literal["standard", "high", "critical"]


class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: f"T-{str(uuid.uuid4())[:6].upper()}")
    title: str
    description: str
    user_email: str
    priority: Literal["low", "medium", "high"]
    status: Literal["open", "in_progress", "resolved"] = "open"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    comments: list[dict] = Field(default_factory=list)
