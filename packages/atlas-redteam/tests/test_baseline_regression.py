from datetime import UTC, datetime

from atlas_redteam.baseline import baseline_from_findings, check_regression
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef


def make_finding(taxonomy_id, asr, ci_low, ci_high, status=FindingStatus.OPEN) -> Finding:
    attempts = 20
    successes = round(asr * attempts)
    return Finding(
        finding_id=f"F-{taxonomy_id}-{status.value}",
        run_id="run-2",
        timestamp=datetime(2026, 8, 9, tzinfo=UTC),
        target_build_sha="b" * 40,
        tool="garak",
        tool_version="0.16.0",
        probe_id="some.Probe",
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id=taxonomy_id)],
        attempts=attempts,
        successes=successes,
        asr=asr,
        asr_ci_low=ci_low,
        asr_ci_high=ci_high,
        seed=1337,
        evidence_path=None,
        repro_command="atlas-redteam run --probe some.Probe --seed 1337",
        status=status,
        control_ref="some-control" if status == FindingStatus.MITIGATED else None,
        retest_run_id=None,
    )


def test_new_finding_not_in_baseline_is_reported_as_new():
    finding = make_finding("LLM01:2026", 0.5, 0.3, 0.7)
    result = check_regression([finding], baseline={})
    assert finding in result.new_findings
    assert not result.has_regression


def test_mitigated_finding_within_baseline_is_ok():
    baseline = {"LLM01:2026": {"asr_ci_low": 0.0, "asr_ci_high": 0.2}}
    finding = make_finding("LLM01:2026", 0.1, 0.05, 0.15, status=FindingStatus.MITIGATED)
    result = check_regression([finding], baseline)
    assert finding in result.ok
    assert not result.has_regression


def test_mitigated_finding_exceeding_baseline_is_a_regression():
    baseline = {"LLM01:2026": {"asr_ci_low": 0.0, "asr_ci_high": 0.2}}
    finding = make_finding("LLM01:2026", 0.6, 0.4, 0.8, status=FindingStatus.MITIGATED)
    result = check_regression([finding], baseline)
    assert finding in result.regressions
    assert result.has_regression


def test_flaky_finding_is_never_a_regression():
    baseline = {"LLM01:2026": {"asr_ci_low": 0.0, "asr_ci_high": 0.2}}
    # asr < 0.05 with wide CI -> flaky, per atlas_schema.Finding.determinism_class
    finding = make_finding("LLM01:2026", 0.02, 0.0, 0.3, status=FindingStatus.MITIGATED)
    result = check_regression([finding], baseline)
    assert finding in result.flaky
    assert not result.has_regression


def test_baseline_from_findings_only_promotes_mitigated():
    open_finding = make_finding("LLM01:2026", 0.5, 0.3, 0.7, status=FindingStatus.OPEN)
    mitigated = make_finding("LLM03:2026", 0.05, 0.0, 0.15, status=FindingStatus.MITIGATED)

    baseline = baseline_from_findings([open_finding, mitigated])

    assert "LLM01:2026" not in baseline
    assert "LLM03:2026" in baseline
    assert baseline["LLM03:2026"]["asr_ci_high"] == 0.15
