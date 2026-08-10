"""Plan deviation (ASI01 — Agent Goal Hijack): atlas_control.plan logs a
DeviationEvent whenever execute_step() is called with an unknown plan_id,
an out-of-range or already-executed step_index, or a denied step — see
that module's docstring. Project 4 wires it to a span event
(atlas.plan.deviation) so it's visible in the trace store, not just a
Python-process-local list; this detector reads it back out.

Not expressible as a flat Sigma field-equals rule because the interesting
fields (plan_id, reason, step_index) live inside the zipped
Events.Name/Events.Attributes arrays with a event-name filter Sigma's
zero-config backend can't combine with a nested map lookup in one rule —
straightforward as a direct query.
"""

from __future__ import annotations

_QUERY = """
SELECT
    TraceId, SpanId, ServiceName, Timestamp,
    t.2['plan_id'] AS PlanId,
    t.2['reason'] AS Reason,
    t.2['step_index'] AS StepIndex
FROM otel.otel_traces
ARRAY JOIN arrayZip(Events.Name, Events.Attributes) AS t
WHERE t.1 = 'atlas.plan.deviation'
"""


def detect(client) -> list[dict]:
    """`client` is a clickhouse_connect Client."""
    result = client.query(_QUERY)
    return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]
