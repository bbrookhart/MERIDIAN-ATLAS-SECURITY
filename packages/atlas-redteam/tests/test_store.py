from datetime import UTC, datetime

from atlas_redteam.store import FindingsStore
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef


def make_finding() -> Finding:
    return Finding(
        finding_id="F-store-test",
        run_id="run-store",
        timestamp=datetime(2026, 8, 9, tzinfo=UTC),
        target_build_sha="c" * 40,
        tool="garak",
        tool_version="0.16.0",
        probe_id="some.Probe",
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id="LLM01:2026")],
        attempts=10,
        successes=5,
        asr=0.5,
        asr_ci_low=0.3,
        asr_ci_high=0.7,
        seed=1337,
        evidence_path="evidence/transcripts/run-store/x.jsonl",
        repro_command="atlas-redteam run --probe some.Probe --seed 1337",
        status=FindingStatus.OPEN,
        control_ref=None,
        retest_run_id=None,
    )


def test_insert_and_round_trip(tmp_path):
    db_path = tmp_path / "findings.duckdb"
    store = FindingsStore(db_path)
    finding = make_finding()
    store.insert(finding)

    by_run = store.by_run("run-store")
    assert len(by_run) == 1
    assert by_run[0].finding_id == finding.finding_id
    assert by_run[0].taxonomy[0].id == "LLM01:2026"

    all_findings = store.all()
    assert len(all_findings) == 1
    store.close()


def test_insert_is_idempotent_on_finding_id(tmp_path):
    db_path = tmp_path / "findings.duckdb"
    store = FindingsStore(db_path)
    finding = make_finding()
    store.insert(finding)
    store.insert(finding)  # same finding_id — should replace, not duplicate

    assert len(store.all()) == 1
    store.close()
