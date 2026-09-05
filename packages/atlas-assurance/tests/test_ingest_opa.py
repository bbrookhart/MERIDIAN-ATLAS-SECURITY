import json
from datetime import UTC, datetime
from pathlib import Path

from atlas_assurance.ingest.opa import parse_opa_json

# Real shape confirmed live via `opa test packages/atlas-control/policy --format json`.
REAL_OPA_ROWS = [
    {
        "location": {"file": "policy/tool_authorization_test.rego", "row": 22, "col": 1},
        "package": "data.atlas.authz_test",
        "name": "test_refund_over_threshold_is_denied_regardless_of_framing",
        "duration": 6918416,
    },
    {
        "location": {"file": "policy/tool_authorization_test.rego", "row": 44, "col": 1},
        "package": "data.atlas.authz_test",
        "name": "test_a_hypothetically_broken_rule",
        "duration": 500000,
        "fail": True,
    },
]


def test_parses_real_opa_json_shape(tmp_path: Path) -> None:
    path = tmp_path / "opa.json"
    path.write_text(json.dumps(REAL_OPA_ROWS))
    ingested_at = datetime(2026, 8, 10, tzinfo=UTC)

    results = parse_opa_json(path, ingested_at=ingested_at)

    assert len(results) == 2
    by_id = {r.test_id: r for r in results}
    passing = by_id[
        "opa::data.atlas.authz_test::test_refund_over_threshold_is_denied_regardless_of_framing"
    ]
    assert passing.passed is True
    assert passing.timestamp == ingested_at
    assert passing.source == "opa"
    assert abs(passing.duration_s - 0.006918416) < 1e-9

    failing = by_id["opa::data.atlas.authz_test::test_a_hypothetically_broken_rule"]
    assert failing.passed is False
