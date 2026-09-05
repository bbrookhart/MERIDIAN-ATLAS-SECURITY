"""Small retry helper shared by replay.py and workload_generator.py.

LLM calls through the real stack occasionally hit a slow response under
load (confirmed live: a Phase 3 run hit an httpx.ReadTimeout mid-run while
Ollama itself was otherwise healthy and responsive within milliseconds
moments later) — a transient infrastructure hiccup, not a code bug, and
not worth failing an entire multi-minute replay run over.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx


def with_retry[T](fn: Callable[[], T], attempts: int = 3, backoff_seconds: float = 2.0) -> T:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            if attempt < attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))
    assert last_exc is not None
    raise last_exc
