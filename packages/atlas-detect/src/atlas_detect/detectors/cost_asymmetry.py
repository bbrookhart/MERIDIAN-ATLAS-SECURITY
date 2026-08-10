"""Cost asymmetry (LLM06:2026 — Unbounded Consumption, reframed around
cost asymmetry in the 2026 edition): flags an agent session whose total
token spend, or spend-per-tool-chaining-round, is disproportionate — the
framing the 2026 OWASP list uses explicitly: reasoning models and tool
chains make a single crafted input disproportionately expensive, not just
"a lot of tokens."

Scoped to the agent surface (/agent/act): that's the only surface this
project instruments with a session-scoped parent span (invoke_agent,
atlas.session_id) to aggregate token usage under — /chat and /rag/query
are single-turn and don't have a chaining-round concept to be
disproportionate relative to. Token counts come from Ollama's own
prompt_eval_count/eval_count, captured as span attributes in
ollama_client.py, not estimated.
"""

from __future__ import annotations

_QUERY = """
WITH sessions AS (
    SELECT TraceId, SpanAttributes['atlas.session_id'] AS SessionId
    FROM otel.otel_traces
    WHERE SpanName = 'invoke_agent'
),
token_usage AS (
    SELECT
        TraceId,
        sum(toInt64OrZero(SpanAttributes['gen_ai.usage.input_tokens'])) AS InputTokens,
        sum(toInt64OrZero(SpanAttributes['gen_ai.usage.output_tokens'])) AS OutputTokens,
        count() AS ChatCalls
    FROM otel.otel_traces
    WHERE SpanName LIKE 'chat %'
    GROUP BY TraceId
)
SELECT
    s.SessionId, s.TraceId,
    t.InputTokens, t.OutputTokens, t.ChatCalls,
    (t.InputTokens + t.OutputTokens) AS TotalTokens
FROM sessions s
JOIN token_usage t ON s.TraceId = t.TraceId
"""


def detect(
    client, total_token_threshold: int = 4000, per_call_token_threshold: int = 1500
) -> list[dict]:
    """`client` is a clickhouse_connect Client. Flags sessions exceeding
    either an absolute total-token threshold or a per-chat-call average —
    the latter catches one disproportionately expensive round even in an
    otherwise-short session."""
    result = client.query(_QUERY)
    rows = [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]

    findings = []
    for row in rows:
        per_call = row["TotalTokens"] / row["ChatCalls"] if row["ChatCalls"] else 0
        over_total = row["TotalTokens"] > total_token_threshold
        over_per_call = per_call > per_call_token_threshold
        if over_total or over_per_call:
            findings.append(
                {
                    **row,
                    "tokens_per_call": per_call,
                    "reason": "total_threshold" if over_total else "per_call_threshold",
                }
            )
    return findings
