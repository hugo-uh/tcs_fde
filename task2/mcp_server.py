"""IT Helpdesk MCP Server — Python + FastAPI.

Exposes the following tools:
  - create_support_ticket: creates a new IT support ticket
  - check_ticket_status: retrieves the status of an existing ticket

Tickets are stored in an in-memory dictionary (lost on restart).

Run with: uvicorn server:app --port 3000
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from mcp.server import MCPServer

mcp_server = MCPServer(name="IT Helpdesk MCP Server", version="1.0.0")

VALID_PRIORITIES = ("low", "medium", "high", "critical")

# In-memory ticket store: ticket_id -> ticket data
tickets: dict[str, dict] = {}


def _format_ticket(ticket: dict) -> str:
    return (
        f"Ticket {ticket['ticket_id']}\n"
        f"  Title: {ticket['title']}\n"
        f"  Description: {ticket['description']}\n"
        f"  Requester: {ticket['requester']}\n"
        f"  Priority: {ticket['priority']}\n"
        f"  Status: {ticket['status']}\n"
        f"  Created at: {ticket['created_at']}"
    )


@mcp_server.tool(
    name="create_support_ticket",
    description="Create a new IT support ticket. Priority: low, medium, high or critical.",
)
def create_support_ticket(
    title: str, description: str, requester: str, priority: str = "medium"
) -> str:
    priority = priority.strip().lower()
    if not title or not description or not requester:
        return "Error: title, description and requester are required."
    if priority not in VALID_PRIORITIES:
        return f"Error: priority must be one of: {', '.join(VALID_PRIORITIES)}."

    ticket_id = f"TCK-{len(tickets) + 1:04d}"
    tickets[ticket_id] = {
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "requester": requester,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return f"Ticket created successfully.\n{_format_ticket(tickets[ticket_id])}"


@mcp_server.tool(
    name="check_ticket_status",
    description="Retrieve the status of an existing IT support ticket by its ticket ID.",
)
def check_ticket_status(ticket_id: str) -> str:
    ticket = tickets.get(ticket_id.strip().upper())
    if ticket is None:
        return f"Ticket '{ticket_id}' not found."
    return _format_ticket(ticket)


mcp_app = mcp_server.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app's own lifespan starts the MCP session manager's task group.
    # FastAPI doesn't run a mounted sub-app's lifespan automatically, so we
    # enter it explicitly here to keep that startup/shutdown tied to ours.
    async with mcp_app.router.lifespan_context(mcp_app):
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/", mcp_app)

if __name__ == "__main__":
    import asyncio
    import sys

    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=3000)
    server = uvicorn.Server(config)

    # On Windows, uvicorn's default event loop is a ProactorEventLoop, which
    # logs a noisy (but harmless) ConnectionResetError whenever a client
    # disconnects abruptly — which our short-lived-connection-per-request
    # client does on every call. Running under a SelectorEventLoop instead
    # avoids that; asyncio.run(loop_factory=...) is the non-deprecated way
    # to choose the loop type (the older set_event_loop_policy is removed
    # in newer Python versions).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None

    print("MCP server running at http://localhost:3000")
    asyncio.run(server.serve(), loop_factory=loop_factory)
