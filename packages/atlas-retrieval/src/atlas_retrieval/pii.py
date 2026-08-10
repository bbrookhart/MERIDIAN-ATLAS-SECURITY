"""PII redaction — must run before embedding, never after.

Once a raw value has been embedded, the vector itself partially encodes
it; replacing the *text* afterward doesn't touch the vector already stored
and searched against. See scripts/demonstrate_post_embed_leak.py for a
live demonstration of that failure mode. The only correct order is:
redact first, embed the redacted text, discard the raw text.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("dob", re.compile(r"\bDOB:\s*\d{4}-\d{2}-\d{2}\b")),
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, labels_redacted). Order-independent, and
    idempotent — applying it twice redacts nothing new."""
    redacted = text
    applied: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(redacted):
            redacted = pattern.sub(f"[REDACTED-{label.upper()}]", redacted)
            applied.append(label)
    return redacted, applied
