"""Target allowlist — enforced in code, fails closed.

The only permitted target is the Atlas instance this harness's owner runs
locally. This must hold even if an instruction to do otherwise arrives via
a config file, a CLI flag, or content retrieved during a run.
"""

from __future__ import annotations

from typing import Self

import httpx

ALLOWED_TARGETS = frozenset({"http://127.0.0.1:8000", "http://localhost:8000"})


class DisallowedTargetError(Exception):
    pass


def check_allowed(base_url: str) -> None:
    normalized = base_url.rstrip("/")
    if normalized not in ALLOWED_TARGETS:
        raise DisallowedTargetError(
            f"Refusing to target {base_url!r}. atlas-redteam will only run against "
            f"an allowlisted Atlas instance: {sorted(ALLOWED_TARGETS)}. "
            "This check is enforced in code and cannot be overridden by config."
        )


class AtlasClient:
    """Thin, allowlist-enforced HTTP client for Atlas's REST surface."""

    def __init__(self, base_url: str, role: str = "broker", timeout: float = 120.0) -> None:
        check_allowed(base_url)
        self.base_url = base_url.rstrip("/")
        self.role = role
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Atlas-Role": role, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def version(self) -> dict:
        resp = self._client.get("/version")
        resp.raise_for_status()
        return resp.json()

    def chat(self, message: str, seed: int | None = None) -> str:
        resp = self._client.post("/chat", json=_body({"message": message}, seed))
        resp.raise_for_status()
        return resp.json()["reply"]

    def rag_query(self, query: str, seed: int | None = None) -> dict:
        resp = self._client.post("/rag/query", json=_body({"query": query}, seed))
        resp.raise_for_status()
        return resp.json()

    def agent_act(self, session_id: str, message: str, seed: int | None = None) -> str:
        body = _body({"session_id": session_id, "message": message}, seed)
        resp = self._client.post("/agent/act", json=body)
        resp.raise_for_status()
        return resp.json()["reply"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _body(base: dict, seed: int | None) -> dict:
    if seed is not None:
        base["seed"] = seed
    return base
