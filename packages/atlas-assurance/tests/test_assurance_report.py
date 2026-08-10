import shutil
import subprocess
from datetime import UTC, datetime

import pytest
from atlas_assurance.ingest.findings import load_findings
from atlas_assurance.ingest.junit import parse_junit
from atlas_assurance.ingest.opa import parse_opa_json
from atlas_assurance.register import REPO_ROOT, build_register
from atlas_assurance.report import render_assurance_report

pytestmark = pytest.mark.skipif(shutil.which("opa") is None, reason="opa binary required on PATH")


@pytest.fixture(scope="module")
def real_register(tmp_path_factory) -> dict:
    tmp_dir = tmp_path_factory.mktemp("report_test")
    junit_path = tmp_dir / "junit.xml"
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

    findings = load_findings()
    return build_register(junit_results + opa_results, findings, generated_at=datetime.now(UTC))


def test_render_assurance_report_produces_valid_looking_html(real_register: dict) -> None:
    output = render_assurance_report(real_register)

    assert output.startswith("<!doctype html>")
    assert "</html>" in output
    assert "atlas-assurance" in output


def test_report_contains_every_control_id(real_register: dict) -> None:
    output = render_assurance_report(real_register)

    for row in real_register["controls"]:
        assert row["control_id"] in output


def test_report_escapes_html_in_not_assessed_reason() -> None:
    from atlas_assurance.report import render_assurance_report

    fake_register = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "controls_assessed": 0,
        "controls_not_assessed": 1,
        "controls_stale": 0,
        "controls": [
            {
                "control_id": "c1",
                "name": "<script>alert(1)</script>",
                "status": "not_assessed",
                "passed": None,
                "freshness": None,
                "last_evidence_at": None,
                "finding_ids": [],
                "not_assessed_reason": "<b>no test found</b>",
            }
        ],
        "aivss": {"findings_scored": 0, "top_divergences": []},
        "coverage_gaps": [],
        "business_translation_top5": [],
        "detection_efficacy": {"available": False, "reason": "n/a"},
    }

    output = render_assurance_report(fake_register)

    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;" in output
