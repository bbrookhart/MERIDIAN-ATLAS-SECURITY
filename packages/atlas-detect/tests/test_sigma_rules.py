"""Each Sigma rule gets a real live test: send a span through the real
Collector (which sets the security.* flags / drift events this rule
looks for, and redacts what it should redact), then run the rule's
pySigma-generated SQL against real ClickHouse and confirm it matches —
and that a clearly-benign span does NOT match. Skipped if the stack isn't
reachable, same as test_redaction.py.
"""

from __future__ import annotations

import time
import uuid

import clickhouse_connect
import httpx
import pytest
from atlas_detect.clickhouse_schema import ensure_views
from atlas_detect.sigma_runner import load_rules, run_rule
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

COLLECTOR_ENDPOINT = "http://127.0.0.1:4318"


def _collector_reachable() -> bool:
    try:
        httpx.get(f"{COLLECTOR_ENDPOINT}/", timeout=1)
        return True
    except httpx.TransportError:
        return False


pytestmark = pytest.mark.skipif(
    not _collector_reachable(),
    reason="otel-collector not reachable — bring up "
    "`docker compose -f packages/atlas/docker-compose.yml up -d clickhouse otel-collector`",
)


@pytest.fixture
def ch_client():
    client = clickhouse_connect.get_client(
        host="127.0.0.1", port=8123, username="default", password="atlas", database="otel"
    )
    ensure_views(client)
    yield client
    client.close()


def _rule(title_substring: str):
    (spec,) = [s for s in load_rules() if title_substring in s.rule.title]
    return spec


def _send_span(span_name: str, event_name: str, attributes: dict) -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": "sigma-test"}))
    exporter = OTLPSpanExporter(endpoint=f"{COLLECTOR_ENDPOINT}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=100))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span(span_name) as span:
        span.add_event(event_name, attributes=attributes)
    provider.shutdown()


def _wait_for_span(
    client, span_name: str, table: str = "otel.otel_traces", timeout_s: float = 10
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = client.query(
            f"SELECT count() FROM {table} WHERE SpanName = {{name:String}}",
            parameters={"name": span_name},
        )
        if result.result_rows[0][0] > 0:
            return
        time.sleep(0.5)
    raise AssertionError(f"span {span_name!r} never landed in {table}")


def test_canary_in_egress_rule_matches_real_canary_and_not_clean_text(ch_client):
    spec = _rule("Canary token")

    canary_span = f"sigma-canary-{uuid.uuid4().hex[:8]}"
    _send_span(
        canary_span,
        "gen_ai.content.completion",
        {"content": f"here is MERIDIAN-CANARY-{uuid.uuid4()}"},
    )
    clean_span = f"sigma-canary-clean-{uuid.uuid4().hex[:8]}"
    _send_span(clean_span, "gen_ai.content.completion", {"content": "what is my policy premium"})
    _wait_for_span(ch_client, canary_span, "otel.span_events_flat")
    _wait_for_span(ch_client, clean_span, "otel.span_events_flat")

    matches = run_rule(ch_client, spec)
    matched_spans = {m["SpanName"] for m in matches}

    assert canary_span in matched_spans
    assert clean_span not in matched_spans


def test_ansi_escape_rule_matches_ansi_and_not_clean_text(ch_client):
    spec = _rule("ANSI escape")

    ansi_span = f"sigma-ansi-{uuid.uuid4().hex[:8]}"
    _send_span(ansi_span, "gen_ai.content.completion", {"content": "click here \x1b[31mnow\x1b[0m"})
    clean_span = f"sigma-ansi-clean-{uuid.uuid4().hex[:8]}"
    _send_span(clean_span, "gen_ai.content.completion", {"content": "no escape codes here"})
    _wait_for_span(ch_client, ansi_span, "otel.span_events_flat")
    _wait_for_span(ch_client, clean_span, "otel.span_events_flat")

    matches = run_rule(ch_client, spec)
    matched_spans = {m["SpanName"] for m in matches}

    assert ansi_span in matched_spans
    assert clean_span not in matched_spans


def test_mcp_drift_rule_matches_drift_event(ch_client):
    spec = _rule("MCP tool description hash drift")

    drift_span = f"sigma-mcp-drift-{uuid.uuid4().hex[:8]}"
    _send_span(
        drift_span,
        "atlas.mcp.description_drift",
        {"server_url": "http://mcp-ticketing:8801/mcp", "tool_name": "create_ticket"},
    )
    clean_span = f"sigma-mcp-clean-{uuid.uuid4().hex[:8]}"
    _send_span(clean_span, "gen_ai.content.completion", {"content": "ordinary completion"})
    _wait_for_span(ch_client, drift_span, "otel.span_events_flat")
    _wait_for_span(ch_client, clean_span, "otel.span_events_flat")

    matches = run_rule(ch_client, spec)
    matched_spans = {m["SpanName"] for m in matches}

    assert drift_span in matched_spans
    assert clean_span not in matched_spans


def test_tool_denied_rule_matches_only_denied_policy_decisions(ch_client):
    """Structural check against whatever policy_decision.tool spans
    already exist from prior live testing (this rule's SpanAttributes
    shape — a Map, not a span event — comes from atlas-control's real
    policy.py, not a synthetic OTLP payload): every match the rule
    returns must actually be a denial, never a false positive on an
    allowed decision."""
    spec = _rule("Tool invocation denied")
    matches = run_rule(ch_client, spec)
    for m in matches:
        assert m["PolicyAllow"] == "false"
        assert m["SpanName"] == "policy_decision.tool"
