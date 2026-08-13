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

`poisoning_sources` is the fix for a measured precision failure. Two
memory sources carry `trust_tier="untrusted"`: `user_input` and
`tool_result` (see `_TRUST_TIER_BY_SOURCE` in atlas.memory). An earlier
version considered both, which scored **precision 0.00 with 25 false
positives** across 65 benign sessions — because a user typing "look up
claim CLM-04821" and the agent then calling `lookup_claim` with that
number is not poisoning, it is the entire intended function of an agent.
The threat ASI06 actually describes is content the *user did not author*
— a retrieved document, an MCP docstore entry, a ticket body — steering a
later privileged call. So `user_input` is excluded by default. This is a
threat-model correction, not a threshold tweak; pass both sources
explicitly to reproduce the old behaviour.
"""

from __future__ import annotations

import json
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


def _arg_values(args_content: str) -> list[str]:
    """Tool arguments as a list of string *values*, not the serialized JSON.

    Measured reason: comparing against the raw JSON blob matched
    structural boilerplate. On a real session the longest shared run
    between a `search_kb` result and a later tool call was `", "body": "`
    — twelve characters of pure punctuation, present in any two JSON
    documents, and completely meaningless as evidence of propagation.
    Comparing value-to-value removes that entire class of false positive.
    """
    try:
        parsed = json.loads(args_content)
    except (json.JSONDecodeError, TypeError):
        return [args_content]

    values: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            values.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(parsed)
    return values


def _is_meaningful(text: str) -> bool:
    """At least half the shared run must be alphanumeric — otherwise it's
    delimiters and whitespace rather than propagated content."""
    alnum = sum(c.isalnum() for c in text)
    return alnum * 2 >= len(text)


POISONING_SOURCES: tuple[str, ...] = ("tool_result",)


def detect(
    atlas_base_url: str,
    session_id: str,
    client,
    min_overlap_chars: int = 12,
    poisoning_sources: tuple[str, ...] = POISONING_SOURCES,
    exact_value_min_chars: int = 6,
) -> list[dict]:
    """`client` is a clickhouse_connect Client. See the module docstring
    for why `user_input` is excluded from `poisoning_sources` by default.
    """
    resp = httpx.get(f"{atlas_base_url}/memory/{session_id}", timeout=30)
    resp.raise_for_status()
    memory_rows = resp.json()
    untrusted_writes = [
        r
        for r in memory_rows
        if r["trust_tier"] == "untrusted" and r["source"] in poisoning_sources
    ]
    if not untrusted_writes:
        return []

    result = client.query(_TOOL_ARGS_QUERY, parameters={"session_id": session_id})
    tool_calls = [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]

    # Text the user typed themselves is not poisoning, even when it round-trips
    # through a tool result. Measured: a user asking about "CLM-04821" produced
    # a tool_result echoing `{"found": false, "claim_number": "CLM-04821"}`,
    # which then matched a later tool call — flagging the user's own request
    # back at them. ASI06 is about content the user did not author.
    user_authored = " ␟ ".join(r["content"] for r in memory_rows if r["source"] == "user_input")

    findings = []
    for write in untrusted_writes:
        for call in tool_calls:
            if call["Timestamp"].isoformat() <= write["created_at"]:
                continue
            for value in _arg_values(call["ArgsContent"]):
                # Two independent signals of propagation:
                #  1. A long shared run inside a larger argument (prose lifted
                #     out of a document into an email body, say).
                #  2. The *whole* argument value appearing verbatim in the
                #     untrusted content. Length is irrelevant here — if the
                #     entire `claim_number` argument is a string the model
                #     could only have read out of a tool result, that is
                #     unambiguous propagation. Measured: the model lifted
                #     `CLM-16875` (9 chars) from a search_kb result straight
                #     into lookup_claim, which a 12-char run threshold missed
                #     entirely. Tuning the global threshold down to 9 to catch
                #     it would have re-admitted the noise this detector was
                #     just fixed for.
                whole_value = len(value) >= exact_value_min_chars and value in write["content"]
                overlap = value if whole_value else _longest_shared_run(write["content"], value)
                if not whole_value and (
                    len(overlap) < min_overlap_chars or not _is_meaningful(overlap)
                ):
                    continue
                if not _is_meaningful(overlap) or overlap in user_authored:
                    continue
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
