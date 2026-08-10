"""Mock internal document store, exposed as a real MCP server.

A data plane separate from the /rag pgvector index — a literal browse
interface (list/get) rather than semantic search, giving later projects a
second, distinct attack surface. Canary #3 lives in one seeded document; see
atlas.mcp_servers.data.seed_documents.
"""

from mcp.server.mcpserver import MCPServer

from atlas.mcp_servers.data import seed_documents

mcp = MCPServer("atlas-docstore")
_documents = seed_documents()


@mcp.tool()
def list_documents() -> list[dict]:
    """List documents in the internal document store."""
    return [{"doc_id": d["doc_id"], "title": d["title"]} for d in _documents.values()]


@mcp.tool()
def get_document(doc_id: str) -> dict:
    """Get a document's full contents by ID."""
    return _documents.get(doc_id, {"error": "not found", "doc_id": doc_id})


def main() -> None:
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8802)


if __name__ == "__main__":
    main()
