"""Mock ticketing system, exposed as a real MCP server."""

from mcp.server.mcpserver import MCPServer

from atlas.mcp_servers.data import seed_tickets

mcp = MCPServer("atlas-ticketing")
_tickets = seed_tickets()


@mcp.tool()
def create_ticket(subject: str, body: str, priority: str = "medium") -> dict:
    """Create a new support ticket."""
    ticket_id = f"TKT-{len(_tickets) + 1:05d}"
    ticket = {
        "ticket_id": ticket_id,
        "subject": subject,
        "body": body,
        "status": "open",
        "priority": priority,
    }
    _tickets[ticket_id] = ticket
    return ticket


@mcp.tool()
def get_ticket(ticket_id: str) -> dict:
    """Get a support ticket by ID."""
    return _tickets.get(ticket_id, {"error": "not found", "ticket_id": ticket_id})


@mcp.tool()
def list_tickets(status: str | None = None) -> list[dict]:
    """List support tickets, optionally filtered by status."""
    values = list(_tickets.values())
    if status:
        values = [t for t in values if t["status"] == status]
    return values


def main() -> None:
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8801)


if __name__ == "__main__":
    main()
