"""DuckDB-backed findings store.

Lives at evidence/findings.duckdb (repo root) — committed, per the
workspace's own convention that evidence reports and the findings database
are the portfolio's proof, while raw transcripts (evidence/transcripts/,
evidence/raw/) stay gitignored because they contain canary values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

import duckdb
from atlas_schema import Finding

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_PATH = REPO_ROOT / "evidence" / "findings.duckdb"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    target_build_sha TEXT NOT NULL,
    tool TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    probe_id TEXT NOT NULL,
    taxonomy_json TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    successes INTEGER NOT NULL,
    asr DOUBLE NOT NULL,
    asr_ci_low DOUBLE NOT NULL,
    asr_ci_high DOUBLE NOT NULL,
    ci_method TEXT NOT NULL,
    status TEXT NOT NULL,
    finding_json TEXT NOT NULL
);
"""


class FindingsStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self.db_path))
        self._conn.execute(_SCHEMA)

    def insert(self, finding: Finding) -> None:
        taxonomy_json = finding.model_dump_json(include={"taxonomy"})
        finding_json = finding.model_dump_json()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO findings VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                finding.finding_id,
                finding.run_id,
                finding.timestamp,
                finding.target_build_sha,
                finding.tool,
                finding.tool_version,
                finding.probe_id,
                taxonomy_json,
                finding.attempts,
                finding.successes,
                finding.asr,
                finding.asr_ci_low,
                finding.asr_ci_high,
                finding.ci_method,
                finding.status.value,
                finding_json,
            ],
        )

    def insert_many(self, findings: list[Finding]) -> None:
        for f in findings:
            self.insert(f)

    def by_run(self, run_id: str) -> list[Finding]:
        rows = self._conn.execute(
            "SELECT finding_json FROM findings WHERE run_id = ? ORDER BY finding_id", [run_id]
        ).fetchall()
        return [Finding.model_validate_json(r[0]) for r in rows]

    def all(self) -> list[Finding]:
        rows = self._conn.execute("SELECT finding_json FROM findings ORDER BY timestamp").fetchall()
        return [Finding.model_validate_json(r[0]) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
