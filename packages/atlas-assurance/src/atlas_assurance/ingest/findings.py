"""Reads Project 1's real findings straight out of `evidence/findings.duckdb`.

Deliberately re-implements the two SELECTs `atlas_redteam.store.
FindingsStore` already has (rather than importing it) so that reading
findings doesn't require installing atlas-redteam's heavy adversarial
tooling (PyRIT, garak, deepteam) — the same dependency-boundary
discipline `atlas-detect` applied to its own dev-only red-team dep. The
schema being read is `atlas_schema.Finding`, the one real shared
contract — nothing here re-derives or reshapes it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
from atlas_schema import Finding

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DB_PATH = REPO_ROOT / "evidence" / "findings.duckdb"


def load_findings(
    run_ids: list[str] | None = None, db_path: Path = DEFAULT_DB_PATH
) -> list[Finding]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        if run_ids is None:
            rows = conn.execute("SELECT finding_json FROM findings ORDER BY timestamp").fetchall()
        else:
            placeholders = ",".join("?" * len(run_ids))
            rows = conn.execute(
                f"SELECT finding_json FROM findings WHERE run_id IN ({placeholders}) "
                "ORDER BY timestamp",
                run_ids,
            ).fetchall()
    finally:
        conn.close()
    return [Finding.model_validate_json(r[0]) for r in rows]


def finding_by_id(finding_id: str, db_path: Path = DEFAULT_DB_PATH) -> Finding | None:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            "SELECT finding_json FROM findings WHERE finding_id = ?", [finding_id]
        ).fetchone()
    finally:
        conn.close()
    return Finding.model_validate_json(row[0]) if row else None
