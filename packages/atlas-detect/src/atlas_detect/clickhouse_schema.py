"""Flattened views over the clickhouseexporter's auto-created `otel_traces`
table.

`otel_traces` stores span events as parallel arrays (`Events.Name`,
`Events.Attributes`) and span-level metadata as a `Map(String, String)`
(`SpanAttributes`) — both real, but not something Sigma's field-equals-
value model or its zero-config ClickHouse backend can address directly
(matching a value inside a `Map` or a zipped array pair needs ClickHouse-
specific syntax, not a plain `field = value`). Rather than write a custom
Sigma pipeline that has to know how to generate that syntax for every rule,
these views normalize the two shapes any detection actually needs into
plain flat columns once, so every Sigma rule and stateful detector queries
a simple table.
"""

from __future__ import annotations

SPAN_EVENTS_FLAT_VIEW = """
CREATE OR REPLACE VIEW otel.span_events_flat AS
SELECT
    TraceId, SpanId, ParentSpanId, ServiceName, SpanName, Timestamp,
    t.1 AS EventName,
    t.2['content'] AS EventContent,
    t.2['role'] AS EventRole,
    t.2['security.canary_detected'] AS CanaryDetected,
    t.2['security.ansi_escape_detected'] AS AnsiEscapeDetected
FROM otel.otel_traces
ARRAY JOIN arrayZip(Events.Name, Events.Attributes) AS t
"""

POLICY_DECISIONS_FLAT_VIEW = """
CREATE OR REPLACE VIEW otel.policy_decisions_flat AS
SELECT
    TraceId, SpanId, ServiceName, SpanName, Timestamp,
    SpanAttributes['atlas.caller_role'] AS CallerRole,
    SpanAttributes['atlas.policy.tool'] AS PolicyTool,
    SpanAttributes['atlas.policy.allow'] AS PolicyAllow,
    SpanAttributes['atlas.policy.rule'] AS PolicyRule,
    SpanAttributes['atlas.policy.denied_count'] AS PolicyDeniedCount
FROM otel.otel_traces
WHERE SpanName IN ('policy_decision.tool', 'policy_decision.retrieval')
"""

ALL_VIEWS = [SPAN_EVENTS_FLAT_VIEW, POLICY_DECISIONS_FLAT_VIEW]


def ensure_views(client) -> None:
    """`client` is a clickhouse_connect Client. Idempotent (CREATE OR
    REPLACE VIEW) — safe to call at the start of every tool that reads
    these views (sigma_runner, detectors, scoring, dashboard), and picks
    up view-definition changes without a manual DROP."""
    for ddl in ALL_VIEWS:
        client.command(ddl)
