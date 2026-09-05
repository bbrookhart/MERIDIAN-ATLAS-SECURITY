"""Loads real Sigma YAML rules and runs them against ClickHouse via
pySigma + pysigma-backend-clickhouse — genuine Sigma rule text translated
to genuine SQL by a maintained backend, not a bespoke interpreter.

`logsource.category` on each rule picks which flattened view (and
matching field-mapping pipeline, see sigma_pipeline.py) it targets:
"span_event" -> otel.span_events_flat, "policy_decision" ->
otel.policy_decisions_flat. Add a category here if a future rule needs a
different view.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sigma.backends.clickhouse import ClickhouseBackend
from sigma.collection import SigmaCollection
from sigma.rule import SigmaRule

from atlas_detect.sigma_pipeline import policy_decision_pipeline, span_event_pipeline

SIGMA_DIR = Path(__file__).resolve().parents[2] / "sigma"

_CATEGORY_CONFIG = {
    "span_event": {
        "table": "otel.span_events_flat",
        "pipeline_factory": span_event_pipeline,
    },
    "policy_decision": {
        "table": "otel.policy_decisions_flat",
        "pipeline_factory": policy_decision_pipeline,
    },
}


@dataclass(frozen=True)
class SigmaRuleSpec:
    rule: SigmaRule
    sql: str
    path: Path


def load_rules(sigma_dir: Path | None = None) -> list[SigmaRuleSpec]:
    sigma_dir = sigma_dir or SIGMA_DIR
    specs = []
    for path in sorted(sigma_dir.glob("*.yml")):
        collection = SigmaCollection.from_yaml(path.read_text())
        (rule,) = collection.rules
        category = rule.logsource.category
        config = _CATEGORY_CONFIG[category]
        backend = ClickhouseBackend(
            processing_pipeline=config["pipeline_factory"](), table_name=config["table"]
        )
        (sql,) = backend.convert(collection)
        specs.append(SigmaRuleSpec(rule=rule, sql=sql, path=path))
    return specs


def run_rule(client, spec: SigmaRuleSpec) -> list[dict]:
    """`client` is a clickhouse_connect Client. Returns matching rows as
    dicts, each tagged with which rule matched."""
    result = client.query(spec.sql)
    rows = [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]
    for row in rows:
        row["_sigma_rule_id"] = str(spec.rule.id)
        row["_sigma_rule_title"] = spec.rule.title
        row["_sigma_level"] = spec.rule.level.name.lower() if spec.rule.level else "unknown"
    return rows


def run_all_rules(client, sigma_dir: Path | None = None) -> dict[str, list[dict]]:
    """Returns {rule_title: [matching rows]} for every rule in sigma_dir."""
    return {spec.rule.title: run_rule(client, spec) for spec in load_rules(sigma_dir)}
