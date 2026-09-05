"""Sigma processing pipeline for this project's flattened ClickHouse views
(see clickhouse_schema.py). Uses pySigma's own documented extension point
(`ProcessingPipeline` + `FieldMappingTransformation`, the same pattern its
built-in Windows/Azure pipelines use) — the mapping here is the identity
mapping in most cases because the views already use these names, but it's
a real pipeline object (`requires_pipeline=False` on the backend, so this
is optional convenience, not a workaround) rather than hand-built SQL
strings, which keeps rule authoring in genuine Sigma YAML.
"""

from __future__ import annotations

from sigma.processing.pipeline import ProcessingItem, ProcessingPipeline
from sigma.processing.transformations import FieldMappingTransformation

SPAN_EVENT_FIELDS = {
    "EventName": "EventName",
    "EventContent": "EventContent",
    "EventRole": "EventRole",
    "CanaryDetected": "CanaryDetected",
    "AnsiEscapeDetected": "AnsiEscapeDetected",
    "ServiceName": "ServiceName",
    "SpanName": "SpanName",
}

POLICY_DECISION_FIELDS = {
    "CallerRole": "CallerRole",
    "PolicyTool": "PolicyTool",
    "PolicyAllow": "PolicyAllow",
    "PolicyRule": "PolicyRule",
    "PolicyDeniedCount": "PolicyDeniedCount",
    "ServiceName": "ServiceName",
    "SpanName": "SpanName",
}


def span_event_pipeline() -> ProcessingPipeline:
    return ProcessingPipeline(
        name="atlas span_events_flat pipeline",
        priority=20,
        items=[
            ProcessingItem(
                identifier="atlas_span_event_fields",
                transformation=FieldMappingTransformation(SPAN_EVENT_FIELDS),
            )
        ],
    )


def policy_decision_pipeline() -> ProcessingPipeline:
    return ProcessingPipeline(
        name="atlas policy_decisions_flat pipeline",
        priority=20,
        items=[
            ProcessingItem(
                identifier="atlas_policy_decision_fields",
                transformation=FieldMappingTransformation(POLICY_DECISION_FIELDS),
            )
        ],
    )
