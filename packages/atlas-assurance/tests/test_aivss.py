"""Hand-checked against the ported formula's own arithmetic (see the
python one-liner in the implementation notes) — not just round-tripped
through the module itself.
"""

from datetime import UTC, datetime

from atlas_assurance.aivss import score_all, score_finding, top_divergences
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef


def _finding(**overrides) -> Finding:
    defaults = {
        "finding_id": "F-test",
        "run_id": "run_x",
        "timestamp": datetime.now(UTC),
        "target_build_sha": "deadbeef",
        "tool": "garak",
        "tool_version": "0.1.0",
        "probe_id": "dan-probe",
        "taxonomy": [TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id="LLM01:2026")],
        "attempts": 10,
        "successes": 9,
        "asr": 0.9,
        "asr_ci_low": 0.6,
        "asr_ci_high": 0.98,
        "seed": 1,
        "evidence_path": None,
        "repro_command": "echo repro",
        "status": FindingStatus.OPEN,
        "control_ref": None,
        "retest_run_id": None,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def test_open_prompt_injection_finding_matches_hand_computed_value() -> None:
    finding = _finding()

    result = score_finding(finding)

    assert result.aivss_score == 0.38
    assert result.cvss_only_score == 3.81
    assert result.primary_metric == "CS"
    assert result.mitigation_multiplier == 1.50


def test_mitigated_refund_bypass_finding_matches_hand_computed_value() -> None:
    finding = _finding(
        probe_id="excessive-agency-probe:refund-threshold-bypass",
        taxonomy=[
            TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id="LLM03:2026"),
            TaxonomyRef(framework=TaxonomyFramework.OWASP_ASI_2026, id="ASI02"),
        ],
        asr=0.0,
        asr_ci_low=0.0,
        asr_ci_high=0.161,
        status=FindingStatus.MITIGATED,
        control_ref="packages/atlas-control/policy/tool_authorization.rego::refund_threshold_cents",
    )

    result = score_finding(finding)

    assert result.aivss_score == 0.13
    assert result.cvss_only_score == 4.17
    assert result.primary_metric == "GV"
    assert result.mitigation_multiplier == 1.00


def test_mitigation_lowers_aivss_score_relative_to_an_otherwise_identical_open_finding() -> None:
    open_finding = _finding(status=FindingStatus.OPEN, asr=0.9, asr_ci_low=0.6, asr_ci_high=0.98)
    mitigated_finding = _finding(
        status=FindingStatus.MITIGATED, asr=0.0, asr_ci_low=0.0, asr_ci_high=0.05
    )

    open_result = score_finding(open_finding)
    mitigated_result = score_finding(mitigated_finding)

    assert mitigated_result.aivss_score < open_result.aivss_score


def test_cvss_only_score_is_blind_to_mitigation_status_unlike_aivss() -> None:
    """The whole point of the side-by-side: cvss_only never looks at
    Finding.status at all, so an otherwise-identical open vs. mitigated
    pair produces the *same* cvss_only_score — exactly the blind spot
    AIVSS's mitigation multiplier exists to correct for.
    """
    open_finding = _finding(status=FindingStatus.OPEN)
    mitigated_finding = _finding(
        status=FindingStatus.MITIGATED, asr=0.0, asr_ci_low=0.0, asr_ci_high=0.98
    )

    assert (
        score_finding(open_finding).cvss_only_score
        == score_finding(mitigated_finding).cvss_only_score
    )


def test_top_divergences_orders_by_aivss_minus_cvss_descending() -> None:
    findings = [
        _finding(finding_id="F-a", status=FindingStatus.OPEN, asr_ci_high=0.98),
        _finding(
            finding_id="F-b",
            status=FindingStatus.MITIGATED,
            asr=0.0,
            asr_ci_low=0.0,
            asr_ci_high=0.05,
        ),
    ]

    results = score_all(findings)
    ranked = top_divergences(results, n=2)

    assert [r.finding_id for r in ranked] == sorted(
        (r.finding_id for r in results),
        key=lambda fid: next(r.divergence for r in results if r.finding_id == fid),
        reverse=True,
    )


def test_score_all_covers_every_real_committed_finding_without_error() -> None:
    from atlas_assurance.ingest.findings import load_findings

    findings = load_findings()
    results = score_all(findings)

    assert len(results) == len(findings)
    assert all(0.0 <= r.aivss_score <= 10.0 for r in results)
    assert all(0.0 <= r.cvss_only_score <= 10.0 for r in results)
