"""Memory writes from untrusted-tier content followed by privileged reads
(ASI06 — Memory & Context Poisoning): correlates Atlas's own memory audit
log (Project 2/3's GET /memory/{session_id} — trust_tier per fact) against
subsequent execute_tool calls in the *same* session, looking for the
untrusted content's text propagating into a later tool call's arguments.

Deliberately narrower than "any tool call after any untrusted write":
every multi-step agent session has a tool_result (always untrusted, see
atlas.memory) followed by more tool calls as completely normal operation
— flagging that pattern alone would fire on nearly every session and mean
nothing. This only flags a *literal, substantial textual overlap* (a
shared contiguous run of >= min_overlap_chars) between the untrusted
content and a later tool call's arguments — real evidence the untrusted
text specifically propagated into a privileged action's parameters, not
just "something happened afterward." A real deployment would want a more
sophisticated propagation-tracking mechanism (e.g. tainting values at the
model-output layer); this is a real, working heuristic with a known
false-negative mode (indirect propagation, e.g. the model paraphrasing
the untrusted content into different words, won't match), stated plainly
rather than overclaimed.
"""

from __future__ import annotations

from difflib import SequenceMatcher

import httpx

_TOOL_ARGS_QUERY = """
SELECT TraceId, SpanId, Timestamp, t.2['content'] AS ArgsContent
FROM otel.otel_traces
ARRAY JOIN arrayZip(Events.Name, Events.Attributes) AS t
WHERE SpanName = 'execute_tool'
  AND SpanAttributes['atlas.session_id'] = {session_id:String}
  AND t.1 = 'gen_ai.content.prompt'
  AND t.2['role'] = 'tool_args'
ORDER BY Timestamp
"""


def _longest_shared_run(a: str, b: str) -> str:
    match = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return a[match.a : match.a + match.size]


def detect(atlas_base_url: str, session_id: str, client, min_overlap_chars: int = 12) -> list[dict]:
    """`client` is a clickhouse_connect Client."""
    resp = httpx.get(f"{atlas_base_url}/memory/{session_id}", timeout=30)
    resp.raise_for_status()
    memory_rows = resp.json()
    untrusted_writes = [r for r in memory_rows if r["trust_tier"] == "untrusted"]
    if not untrusted_writes:
        return []

    result = client.query(_TOOL_ARGS_QUERY, parameters={"session_id": session_id})
    tool_calls = [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]

    findings = []
    for write in untrusted_writes:
        for call in tool_calls:
            if call["Timestamp"].isoformat() <= write["created_at"]:
                continue
            overlap = _longest_shared_run(write["content"], call["ArgsContent"])
            if len(overlap) >= min_overlap_chars:
                findings.append(
                    {
                        "session_id": session_id,
                        "untrusted_source": write["source"],
                        "untrusted_written_at": write["created_at"],
                        "tool_call_trace_id": call["TraceId"],
                        "tool_call_at": call["Timestamp"].isoformat(),
                        "shared_text": overlap,
                    }
                )
    return findings
