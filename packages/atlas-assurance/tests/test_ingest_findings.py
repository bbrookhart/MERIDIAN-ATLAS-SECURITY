"""Reads the real, committed evidence/findings.duckdb — proving this
reimplementation matches atlas_redteam.store.FindingsStore's own real
data, not a synthetic fixture.
"""

from atlas_assurance.ingest.findings import DEFAULT_DB_PATH, finding_by_id, load_findings


def test_default_db_path_points_at_the_real_committed_db() -> None:
    assert DEFAULT_DB_PATH.name == "findings.duckdb"
    assert DEFAULT_DB_PATH.exists()


def test_load_findings_returns_real_committed_findings() -> None:
    findings = load_findings()

    assert len(findings) >= 20
    run_ids = {f.run_id for f in findings}
    assert "phase_c_highn" in run_ids


def test_load_findings_filters_by_run_id() -> None:
    findings = load_findings(run_ids=["phase_c_highn"])

    assert len(findings) > 0
    assert all(f.run_id == "phase_c_highn" for f in findings)


def test_a_known_mitigated_finding_has_its_real_control_ref() -> None:
    findings = load_findings(run_ids=["phase_c_highn"])
    refund = next(
        f for f in findings if f.probe_id == "excessive-agency-probe:refund-threshold-bypass"
    )

    assert refund.status.value == "mitigated"
    assert (
        refund.control_ref
        == "packages/atlas-control/policy/tool_authorization.rego::refund_threshold_cents"
    )


def test_finding_by_id_round_trips() -> None:
    some = load_findings(run_ids=["phase_c_highn"])[0]

    fetched = finding_by_id(some.finding_id)

    assert fetched is not None
    assert fetched.finding_id == some.finding_id


def test_finding_by_id_returns_none_for_a_fabricated_id() -> None:
    assert finding_by_id("F-this-id-does-not-exist") is None
