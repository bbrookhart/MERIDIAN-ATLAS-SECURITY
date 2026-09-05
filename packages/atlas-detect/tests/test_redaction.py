"""Proves the Collector's redaction processor actually strips canary
values and PII from span event bodies before they land in ClickHouse —
not just that the config is well-formed. Sends a real OTLP payload
through a live Collector container (via `docker compose up clickhouse
otel-collector`, published on 127.0.0.1:4318/8123) and queries ClickHouse
directly for what actually got stored.

Skipped automatically if the Collector isn't reachable — this test
exercises live infrastructure, not a mock, so it needs the stack up; see
packages/atlas-detect/README.md for the exact compose command.
"""

from __future__ import annotations

import time
import uuid

import clickhouse_connect
import httpx
import pytest
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

COLLECTOR_ENDPOINT = "http://127.0.0.1:4318"
CLICKHOUSE_HOST = "127.0.0.1"


def _collector_reachable() -> bool:
    try:
        httpx.get(f"{COLLECTOR_ENDPOINT}/", timeout=1)
        return True
    except httpx.TransportError:
        return False


pytestmark = pytest.mark.skipif(
    not _collector_reachable(),
    reason="otel-collector not reachable on 127.0.0.1:4318 — bring up "
    "`docker compose -f packages/atlas/docker-compose.yml up -d clickhouse otel-collector`",
)


def _send_span(span_name: str, content: str) -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": "test-redaction"}))
    exporter = OTLPSpanExporter(endpoint=f"{COLLECTOR_ENDPOINT}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=100))
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span(span_name) as span:
        span.add_event("gen_ai.content.prompt", attributes={"role": "user", "content": content})

    provider.shutdown()  # flushes the batch processor synchronously


def _query_event_content(client, span_name: str) -> str:
    for _ in range(20):
        result = client.query(
            "SELECT Events.Attributes FROM otel_traces WHERE SpanName = {span_name:String}",
            parameters={"span_name": span_name},
        )
        if result.result_rows:
            return result.result_rows[0][0][0]["content"]
        time.sleep(0.5)
    raise AssertionError(f"span {span_name!r} never landed in ClickHouse")


@pytest.fixture
def ch_client():
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=8123, username="default", password="atlas", database="otel"
    )
    yield client
    client.close()


def test_canary_value_is_redacted_before_landing_in_clickhouse(ch_client):
    span_name = f"redaction-test-canary-{uuid.uuid4().hex[:8]}"
    real_canary = f"MERIDIAN-CANARY-{uuid.uuid4()}"
    _send_span(span_name, f"the internal reference token is {real_canary}")

    stored_content = _query_event_content(ch_client, span_name)

    assert real_canary not in stored_content
    assert "[REDACTED-CANARY]" in stored_content


def test_ssn_is_redacted_before_landing_in_clickhouse(ch_client):
    span_name = f"redaction-test-ssn-{uuid.uuid4().hex[:8]}"
    _send_span(span_name, "employee ssn is 078-05-1120, salary band B2")

    stored_content = _query_event_content(ch_client, span_name)

    assert "078-05-1120" not in stored_content
    assert "[REDACTED-SSN]" in stored_content


def test_content_with_no_sensitive_pattern_passes_through_unmodified(ch_client):
    span_name = f"redaction-test-clean-{uuid.uuid4().hex[:8]}"
    clean_text = "what is the premium for a home coverage policy"
    _send_span(span_name, clean_text)

    stored_content = _query_event_content(ch_client, span_name)

    assert stored_content == clean_text
