"""Parses real `opa test <policy-dir> --format json` output.

Confirmed live against this repo's actual policy tests: each row has
`location.file`, `package`, `name`, `duration` (nanoseconds) — and, on a
failing test, a `fail: true` field. There is no per-test (or per-run)
timestamp in the format at all, so unlike JUnit, the ingestion time is
the only honest timestamp available here — that's stated in the field
name (`ingested_at`), not disguised as a real test-execution time.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from atlas_assurance.models import TestResult


def parse_opa_json(path: Path, ingested_at: datetime) -> list[TestResult]:
    rows = json.loads(path.read_text())
    results: list[TestResult] = []
    for row in rows:
        failed = bool(row.get("fail")) or bool(row.get("error"))
        results.append(
            TestResult(
                test_id=f"opa::{row['package']}::{row['name']}",
                passed=not failed,
                timestamp=ingested_at,
                duration_s=row.get("duration", 0) / 1e9,
                source="opa",
            )
        )
    return results
