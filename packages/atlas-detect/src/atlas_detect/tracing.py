"""Shared tracer setup for both live services (`atlas`, `atlas-control`).

One function, called once from each service's FastAPI lifespan, so both
services emit spans the same way against the same Collector.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer


def configure_tracing(service_name: str, otlp_endpoint: str | None) -> Tracer:
    """Configure a process-global TracerProvider and return a Tracer for
    `service_name`. If `otlp_endpoint` is falsy (e.g. telemetry disabled
    in a test/dev environment with no Collector running), spans are still
    created but never exported — callers don't need to branch on whether
    telemetry is configured.

    Also instruments httpx client calls: atlas's calls to atlas-control
    (plan submission, step execution, retrieval authorization) get W3C
    trace-context headers injected automatically, and atlas-control's
    FastAPI app (instrumented separately via `instrument_fastapi_app`)
    extracts them — so a request that crosses the atlas -> atlas-control
    network hop is one linked trace, not two disconnected ones.
    """
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    return trace.get_tracer(service_name)


def instrument_fastapi_app(app: Any) -> None:
    """Extracts W3C trace-context from incoming requests and creates a
    server span per request, so an instrumented client's call (see
    `configure_tracing`) links into this service's spans as one trace."""
    FastAPIInstrumentor.instrument_app(app)
