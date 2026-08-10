from datetime import UTC, datetime

from atlas_redteam.coverage import build_coverage_matrix
from atlas_redteam.report import render_report
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef


def make_finding(tool: str, probe_id: str, taxonomy_id: str) -> Finding:
    return Finding(
        finding_id=f"F-{tool}-{probe_id}",
        run_id="run-report",
        timestamp=datetime(2026, 8, 9, tzinfo=UTC),
        target_build_sha="f" * 40,
        tool=tool,
        tool_version="0.1.0",
        probe_id=probe_id,
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id=taxonomy_id)],
        attempts=10,
        successes=5,
        asr=0.5,
        asr_ci_low=0.3,
        asr_ci_high=0.7,
        seed=1337,
        evidence_path=None,
        repro_command=f"atlas-redteam run --probe {probe_id}",
        status=FindingStatus.OPEN,
        control_ref=None,
        retest_run_id=None,
    )


def test_render_report_produces_valid_html_shell():
    findings = [make_finding("garak", "probe-a", "LLM01:2026")]
    coverage = build_coverage_matrix({"garak:probe-a": ["LLM01:2026"]})

    html_doc = render_report("run-report-test", "d" * 40, findings, coverage)

    assert html_doc.startswith("<!doctype html>")
    assert "run-report-test" in html_doc
    assert "garak:probe-a" in html_doc
    assert "LLM01:2026" in html_doc


def test_render_report_escapes_html_in_probe_ids():
    findings = [make_finding("garak", "<script>alert(1)</script>", "LLM01:2026")]
    coverage = build_coverage_matrix({})

    html_doc = render_report("run-x", "e" * 40, findings, coverage)

    assert "<script>alert(1)</script>" not in html_doc
    assert "&lt;script&gt;" in html_doc
