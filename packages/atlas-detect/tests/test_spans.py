"""Proves the events-not-attributes rule at the SDK level, with a real
OTel TracerProvider and an in-memory exporter — no live Collector needed
to verify this specific property.
"""

from atlas_detect.semconv import EVENT_COMPLETION, EVENT_PROMPT
from atlas_detect.spans import record_completion_event, record_prompt_event
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _tracer_with_memory_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def test_prompt_content_lands_in_an_event_not_a_span_attribute():
    tracer, exporter = _tracer_with_memory_exporter()

    with tracer.start_as_current_span("chat") as span:
        record_prompt_event(span, "user", "what is my account balance")

    (recorded_span,) = exporter.get_finished_spans()

    assert "what is my account balance" not in (recorded_span.attributes or {}).values()
    assert len(recorded_span.events) == 1
    event = recorded_span.events[0]
    assert event.name == EVENT_PROMPT
    assert event.attributes["content"] == "what is my account balance"
    assert event.attributes["role"] == "user"


def test_completion_content_lands_in_an_event_not_a_span_attribute():
    tracer, exporter = _tracer_with_memory_exporter()

    with tracer.start_as_current_span("chat") as span:
        record_completion_event(span, "your balance is $500")

    (recorded_span,) = exporter.get_finished_spans()

    assert "your balance is $500" not in (recorded_span.attributes or {}).values()
    event = recorded_span.events[0]
    assert event.name == EVENT_COMPLETION
    assert event.attributes["content"] == "your balance is $500"


def test_span_attributes_never_contain_message_content_alongside_metadata():
    """Regression guard: a call site that mistakenly does
    span.set_attribute("content", ...) instead of going through
    record_prompt_event/record_completion_event would defeat the entire
    redaction strategy (the Collector only scrubs event bodies). This test
    documents the property those two helpers exist to guarantee."""
    tracer, exporter = _tracer_with_memory_exporter()

    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        record_prompt_event(span, "user", "MERIDIAN-CANARY-should-not-be-an-attribute")

    (recorded_span,) = exporter.get_finished_spans()
    assert "MERIDIAN-CANARY-should-not-be-an-attribute" not in str(recorded_span.attributes)
