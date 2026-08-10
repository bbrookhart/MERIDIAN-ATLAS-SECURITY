"""Integration test: real `pytest --junitxml` output (generated live
against atlas-control's actual suite), real `opa test --format json`
output (generated live via the real `opa` binary — required on PATH,
same convention atlas-control's own tests already use, no skip/mock),
and the real committed findings DB, run through the full register build.
"""

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from atlas_assurance.ingest.findings import load_findings
from atlas_assurance.ingest.junit import parse_junit
from atlas_assurance.ingest.opa import parse_opa_json
from atlas_assurance.register import REPO_ROOT, build_register

pytestmark = pytest.mark.skipif(shutil.which("opa") is None, reason="opa binary required on PATH")


@pytest.fixture(scope="module")
def real_test_results(tmp_path_factory) -> list:
    tmp_dir = tmp_path_factory.mktemp("register_integration")

    junit_path = tmp_dir / "atlas_control_junit.xml"
    subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "atlas-control",
            "pytest",
            str(REPO_ROOT / "packages" / "atlas-control"),
            "-q",
            f"--junitxml={junit_path}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    junit_results = parse_junit(junit_path, package="atlas-control")

    opa_result = subprocess.run(
        [
            "opa",
            "test",
            str(REPO_ROOT / "packages" / "atlas-control" / "policy"),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    opa_json_path = tmp_dir / "opa.json"
    opa_json_path.write_text(opa_result.stdout)
    opa_results = parse_opa_json(opa_json_path, ingested_at=datetime.now(UTC))

    return junit_results + opa_results


def test_build_register_against_real_live_artifacts(real_test_results: list) -> None:
    findings = load_findings()

    register = build_register(real_test_results, findings, generated_at=datetime.now(UTC))

    assert register["controls_assessed"] > 0
    assert register["controls_assessed"] + register["controls_not_assessed"] == len(
        register["controls"]
    )
    assert register["aivss"]["findings_scored"] == len(findings)
    assert len(register["business_translation_top5"]) == 5


def test_assessed_controls_that_are_fresh_and_passing_have_no_not_assessed_reason(
    real_test_results: list,
) -> None:
    findings = load_findings()
    register = build_register(real_test_results, findings, generated_at=datetime.now(UTC))

    fresh_passing = [
        r
        for r in register["controls"]
        if r["status"] == "assessed" and r["passed"] and r["freshness"] == "fresh"
    ]
    assert len(fresh_passing) > 0
    assert all(r["not_assessed_reason"] is None for r in fresh_passing)


def test_the_real_committed_refund_threshold_control_is_assessed_and_passing(
    real_test_results: list,
) -> None:
    findings = load_findings()
    register = build_register(real_test_results, findings, generated_at=datetime.now(UTC))

    row = next(
        r for r in register["controls"] if r["control_id"] == "tool-authorization-refund-threshold"
    )
    assert row["status"] == "assessed"
    assert row["passed"] is True
    assert "F-" in row["finding_ids"][0]  # linked to a real Finding, sourced from the DB


def test_register_is_json_serializable(real_test_results: list) -> None:
    findings = load_findings()
    register = build_register(real_test_results, findings, generated_at=datetime.now(UTC))

    json.dumps(register)  # must not raise


def test_detection_efficacy_reads_the_real_committed_project4_artifact(
    real_test_results: list,
) -> None:
    findings = load_findings()
    register = build_register(real_test_results, findings, generated_at=datetime.now(UTC))

    de = register["detection_efficacy"]
    if (REPO_ROOT / "packages" / "atlas-detect" / "scripts" / "phase3_results.json").exists():
        assert de["available"] is True
        assert "scores" in de
    else:
        assert de["available"] is False


def test_missing_phase3_file_is_reported_not_assessed_not_hidden(
    real_test_results: list, tmp_path: Path
) -> None:
    findings = load_findings()
    register = build_register(
        real_test_results,
        findings,
        generated_at=datetime.now(UTC),
        phase3_path=tmp_path / "nonexistent.json",
    )

    assert register["detection_efficacy"] == {
        "available": False,
        "reason": (
            f"{tmp_path / 'nonexistent.json'} not found — Project 4's phase3_results.json requires its live "
            "ClickHouse/Collector stack, which this build did not bring up"
        ),
    }
