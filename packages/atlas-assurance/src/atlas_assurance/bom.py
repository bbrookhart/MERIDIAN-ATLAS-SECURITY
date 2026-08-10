"""AI-BOM (CycloneDX) — models, MCP tool surfaces (with the same
description hashes `atlas_control.mcp_client` pins at runtime), and the
full transitive dependency graph.

Tool description hashes are computed with the real `_hash_description`
from `atlas_control.mcp_client` (reused, not reimplemented) against each
MCP server's own live `ToolManager.list_tools()` — the exact same
`description` string a real client would see and pin on first contact —
rather than a live network round-trip to a running server, so the BOM can
be generated in CI without docker-compose up.

Transitive dependencies are read directly from the repo-root `uv.lock`
(already a full, exact, hashed resolution — no separate `uv export`
needed).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from atlas.config import settings
from atlas.mcp_servers import docstore, ticketing
from atlas_control.mcp_client import _hash_description
from cyclonedx.model import Property
from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.model.service import Service
from cyclonedx.output.json import JsonV1Dot5

REPO_ROOT = Path(__file__).resolve().parents[4]
LOCKFILE_PATH = REPO_ROOT / "uv.lock"

_MCP_SERVERS = (
    ("atlas-docstore", docstore.mcp, 8802),
    ("atlas-ticketing", ticketing.mcp, 8801),
)


def _model_components() -> list[Component]:
    return [
        Component(
            name=settings.ollama_chat_model,
            type=ComponentType.MACHINE_LEARNING_MODEL,
            version=settings.ollama_chat_model,
            bom_ref=f"model:chat:{settings.ollama_chat_model}",
            properties=[
                Property(name="atlas:role", value="chat"),
                Property(name="atlas:provider", value=settings.model_provider),
            ],
        ),
        Component(
            name=settings.ollama_embed_model,
            type=ComponentType.MACHINE_LEARNING_MODEL,
            version=settings.ollama_embed_model,
            bom_ref=f"model:embed:{settings.ollama_embed_model}",
            properties=[
                Property(name="atlas:role", value="embedding"),
                Property(name="atlas:embed_dimensions", value=str(settings.embed_dimensions)),
            ],
        ),
    ]


def _mcp_services() -> list[Service]:
    services = []
    for server_name, mcp_server, port in _MCP_SERVERS:
        tools = mcp_server._tool_manager.list_tools()
        properties = [Property(name="atlas:mcp:port", value=str(port))]
        for tool in sorted(tools, key=lambda t: t.name):
            digest = _hash_description(tool.description or "")
            properties.append(Property(name=f"atlas:mcp:tool_hash:{tool.name}", value=digest))
        services.append(
            Service(
                name=server_name,
                bom_ref=f"mcp-service:{server_name}",
                description=f"Atlas MCP server ({len(tools)} tools)",
                properties=properties,
            )
        )
    return services


def _load_lock_packages() -> list[dict]:
    data = tomllib.loads(LOCKFILE_PATH.read_text())
    return data["package"]


def _library_components() -> list[Component]:
    components = []
    for pkg in _load_lock_packages():
        name = pkg["name"]
        version = pkg.get("version")
        if version is None:
            continue  # workspace-member packages (atlas, atlas-control, ...) have no pypi version
        components.append(
            Component(
                name=name,
                type=ComponentType.LIBRARY,
                version=version,
                bom_ref=f"pypi:{name}@{version}",
            )
        )
    return components


def build_bom() -> Bom:
    bom = Bom()
    bom.metadata.component = Component(
        name="atlas", type=ComponentType.APPLICATION, version=settings.build_sha
    )
    all_components = _model_components() + _library_components()
    for component in all_components:
        bom.components.add(component)
    for service in _mcp_services():
        bom.services.add(service)
    # Declares direct dependencies of the root so CycloneDX's dependency
    # graph is complete (this is an inventory BOM, not a resolved call
    # graph, so every top-level component is listed as a direct edge).
    bom.register_dependency(bom.metadata.component, all_components)
    return bom


def emit_cyclonedx_json(bom: Bom) -> str:
    return JsonV1Dot5(bom).output_as_string()


def normalize_for_drift_check(bom_json: dict) -> dict:
    """Strips the fields that are expected to change on every single
    regeneration and carry no real inventory information — `serialNumber`
    is a fresh random UUID per BOM, `bom-ref`s are random per component,
    `metadata.timestamp` is the generation time. Comparing normalized
    snapshots (name/version/type/properties only) is what actually
    detects a real inventory change; comparing raw JSON would report
    "drift" on every single run even when nothing real changed.
    """
    components = sorted(
        (
            c.get("type"),
            c.get("name"),
            c.get("version"),
            tuple(sorted((p["name"], p["value"]) for p in c.get("properties", []))),
        )
        for c in bom_json.get("components", [])
    )
    services = sorted(
        (
            s.get("name"),
            tuple(sorted((p["name"], p["value"]) for p in s.get("properties", []))),
        )
        for s in bom_json.get("services", [])
    )
    return {"components": components, "services": services}
