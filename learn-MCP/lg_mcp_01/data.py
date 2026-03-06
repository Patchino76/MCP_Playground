"""
data.py — In-memory data store for the IT Support Ticket Assistant
==================================================================
This is our "database". In a real app these would be DB queries.
We pre-populate some users and tickets so the agent has something
to search through.
"""

from schema import UserProfile, Ticket

# ── User profiles ─────────────────────────────────────────────────────────────

user_profiles: list[UserProfile] = [
    UserProfile(
        email="alice@company.com",
        name="Alice Johnson",
        department="Engineering",
        machine="Dell XPS 15",
        sla_tier="high",
    ),
    UserProfile(
        email="bob@company.com",
        name="Bob Smith",
        department="Marketing",
        machine="MacBook Pro 14",
        sla_tier="standard",
    ),
    UserProfile(
        email="carol@company.com",
        name="Carol White",
        department="IT",
        machine="ThinkPad X1 Carbon",
        sla_tier="critical",
    ),
]

# ── Existing tickets ───────────────────────────────────────────────────────────
# Pre-seeded so the agent can find duplicates during a demo run.

tickets: list[Ticket] = [
    Ticket(
        id="T-AA1B2C",
        title="VPN disconnects every 30 minutes",
        description="VPN drops connection repeatedly, affecting remote work.",
        user_email="bob@company.com",
        priority="medium",
        status="open",
        created_at="2026-02-18T09:00:00",
    ),
    Ticket(
        id="T-DD3E4F",
        title="Outlook not syncing emails",
        description="Outlook inbox stuck, emails not arriving since Monday.",
        user_email="alice@company.com",
        priority="high",
        status="in_progress",
        created_at="2026-02-19T14:30:00",
    ),
]
