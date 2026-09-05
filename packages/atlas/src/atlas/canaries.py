"""Deterministic canary generation.

Canary values are computed at runtime from a fixed namespace UUID and a seed,
never written as literal strings — the repo's pre-commit hook blocks any
staged diff matching MERIDIAN-CANARY-[0-9a-f], and independent processes
(atlas-api, seed, mcp-docstore) need to derive the identical value with no
shared state.
"""

import uuid

_NAMESPACE = uuid.UUID("6f6b6f8e-9c2a-4b7a-9d1e-6a2f6a2f6a2f")


def _canary(seed: int, label: str) -> str:
    token = uuid.uuid5(_NAMESPACE, f"{seed}:{label}")
    return f"MERIDIAN-CANARY-{token}"


def system_prompt_canary(seed: int) -> str:
    return _canary(seed, "system-prompt")


def hr_doc_canary(seed: int) -> str:
    return _canary(seed, "hr-document")


def docstore_canary(seed: int) -> str:
    return _canary(seed, "mcp-docstore")
