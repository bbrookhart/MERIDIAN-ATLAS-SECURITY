"""Regression guard for a real bug found during Project 2: `atlas-redteam
baseline --run-id X` used to overwrite baseline.json wholesale with only
run X's mitigated findings, silently dropping every earlier project's
already-promoted entries the moment a second project's baseline command
ran. baseline.json is meant to accumulate across projects — promoting a
new run must merge into the existing file, not replace it.
"""

import argparse
from datetime import UTC, datetime

from atlas_redteam.cli import cmd_baseline
from atlas_redteam.store import FindingsStore
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef


def _finding(run_id, taxonomy_id, status=FindingStatus.MITIGATED) -> Finding:
    return Finding(
        finding_id=f"F-{run_id}-{taxonomy_id}",
        run_id=run_id,
        timestamp=datetime(2026, 8, 9, tzinfo=UTC),
        target_build_sha="d" * 40,
        tool="atlas-redteam",
        tool_version="0.1.0",
        probe_id="some-probe",
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id=taxonomy_id)],
        attempts=20,
        successes=0,
        asr=0.0,
        asr_ci_low=0.0,
        asr_ci_high=0.16,
        seed=1337,
        evidence_path=None,
        repro_command="atlas-redteam run --probe some-probe --seed 1337",
        status=status,
        control_ref="some-control" if status == FindingStatus.MITIGATED else None,
        retest_run_id=None,
    )


def test_promoting_a_second_run_preserves_the_first_runs_entries(tmp_path):
    db_path = tmp_path / "findings.duckdb"
    baseline_path = tmp_path / "baseline.json"

    store = FindingsStore(db_path)
    store.insert(_finding("run-project-3", "ASI06"))
    store.close()

    cmd_baseline(
        argparse.Namespace(run_id="run-project-3", db=str(db_path), baseline=str(baseline_path))
    )

    store = FindingsStore(db_path)
    store.insert(_finding("run-project-2", "LLM02:2026"))
    store.close()

    cmd_baseline(
        argparse.Namespace(run_id="run-project-2", db=str(db_path), baseline=str(baseline_path))
    )

    import json

    baseline = json.loads(baseline_path.read_text())
    assert "ASI06" in baseline  # from the first project's promotion — must survive
    assert "LLM02:2026" in baseline  # from the second project's promotion
