"""Tool-call sequence anomaly: flags a tool-to-tool transition (bigram)
never observed in a learned baseline of normal agent workflows.

The baseline is built from the Phase 3 benign workload generator's
traffic — every session it creates uses the `workload-benign-` session_id
prefix (see workload_generator.py), which is how this module tells
"normal traffic to learn from" apart from "traffic to evaluate" without a
separate labeling side-channel. A session with only zero or one tool call
has no bigram at all and is not itself anomalous — the absence of a
transition isn't a transition.
"""

from __future__ import annotations

_SEQUENCE_QUERY = """
WITH sessions AS (
    SELECT TraceId, SpanAttributes['atlas.session_id'] AS SessionId
    FROM otel.otel_traces
    WHERE SpanName = 'invoke_agent' AND SpanAttributes['atlas.session_id'] LIKE {pattern:String}
),
tool_calls AS (
    SELECT TraceId, Timestamp, SpanAttributes['gen_ai.tool.name'] AS ToolName
    FROM otel.otel_traces
    WHERE SpanName = 'execute_tool'
),
sequences AS (
    SELECT TraceId, arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((Timestamp, ToolName)))) AS ToolSequence
    FROM tool_calls
    GROUP BY TraceId
)
SELECT s.SessionId, s.TraceId, seq.ToolSequence
FROM sessions s
JOIN sequences seq ON s.TraceId = seq.TraceId
"""


def _bigrams(sequence: list[str]) -> set[tuple[str, str]]:
    return {(sequence[i], sequence[i + 1]) for i in range(len(sequence) - 1)}


def _fetch_sequences(client, session_pattern: str) -> list[tuple[str, str, list[str]]]:
    result = client.query(_SEQUENCE_QUERY, parameters={"pattern": session_pattern})
    return list(result.result_rows)


def build_baseline(client, session_pattern: str = "workload-benign-%") -> set[tuple[str, str]]:
    """`client` is a clickhouse_connect Client. Returns the set of
    tool-to-tool bigrams observed anywhere in benign traffic."""
    baseline: set[tuple[str, str]] = set()
    for _session_id, _trace_id, sequence in _fetch_sequences(client, session_pattern):
        baseline |= _bigrams(sequence)
    return baseline


def detect(
    client, baseline: set[tuple[str, str]], session_pattern: str = "replay-attack-%"
) -> list[dict]:
    """Returns one entry per (trace, unseen bigram) pair found in traffic
    matching `session_pattern` that isn't in `baseline`."""
    findings = []
    for session_id, trace_id, sequence in _fetch_sequences(client, session_pattern):
        for bigram in _bigrams(sequence):
            if bigram not in baseline:
                findings.append(
                    {
                        "SessionId": session_id,
                        "TraceId": trace_id,
                        "ToolSequence": sequence,
                        "UnseenTransition": bigram,
                    }
                )
    return findings
