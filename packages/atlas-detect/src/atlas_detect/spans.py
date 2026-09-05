"""The one place message content is allowed to touch a span.

WHY EVENTS, NOT ATTRIBUTES (stated once, here, rather than at every call
site): span *attributes* are what tracing backends index for search and
filtering, and OTel SDKs size-cap them — neither property is what you
want for a full prompt or completion. Span *attributes* also travel to
the backend as first-class searchable fields; putting raw conversation
content there means every model interaction is now indexed, and PII in a
customer's message becomes PII in your observability backend. Span
*events* are structurally separate — a Collector processor can be
configured to redact or drop event bodies specifically, before export,
without touching the span-level attributes (operation name, model, role,
policy decision) that are actually useful to search on. See
`packages/atlas-detect/collector-config.yaml`'s `transform` processor,
which does exactly that, and `tests/test_redaction.py`, which proves it.

Every call site in `atlas` and `atlas-control` that needs to record
prompt/completion/query text calls through these two functions — never
`span.set_attribute()` for content. That's the enforcement mechanism:
one file to audit, not a convention to remember at every call site.
"""

from __future__ import annotations

from opentelemetry.trace import Span

from atlas_detect.semconv import EVENT_COMPLETION, EVENT_PROMPT


def record_prompt_event(span: Span, role: str, content: str) -> None:
    span.add_event(EVENT_PROMPT, attributes={"role": role, "content": content})


def record_completion_event(span: Span, content: str) -> None:
    span.add_event(EVENT_COMPLETION, attributes={"content": content})
