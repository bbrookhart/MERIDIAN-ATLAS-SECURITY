"""Regression tests for two bugs found by running the real pipeline
against real data (not by unit-testing in isolation) — see
`_resolve_assertions`' docstring for both.
"""

from datetime import UTC, datetime, timedelta

from atlas_assurance.aivss import score_all
from atlas_assurance.business_translation import top_business_translations
from atlas_assurance.evidence_store import record_assertion
from atlas_assurance.models import ControlDef, TestResult
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef

_NOW = datetime(2026, 8, 10, tzinfo=UTC)

_ASI01_CONTROL = ControlDef(
    control_id="frozen-plan-execution",
    name="Plan frozen before execution",
    description="...",
    control_ref="pkg/plan.py::execute_step",
    test_ref="atlas-control::tests.test_plan::test_it",
    max_age_days=30,
    addresses_taxonomy=("ASI01",),
)
_LLM01_CONTROL = ControlDef(
    control_id="untrusted-context-trust-boundary",
    name="Retrieved chunks marked untrusted",
    description="...",
    control_ref="pkg/trust_boundary.py::wrap_chunk",
    test_ref="atlas-retrieval::tests.test_trust::test_it",
    max_age_days=30,
    addresses_taxonomy=("LLM01:2026",),
)


def _passing(test_ref: str) -> TestResult:
    return TestResult(
        test_id=test_ref, passed=True, timestamp=_NOW, duration_s=0.1, source="pytest"
    )


def _finding(finding_id: str, taxonomy_ids: list[str], **overrides) -> Finding:
    defaults = {
        "finding_id": finding_id,
        "run_id": "phase_a_agent_baseline",
        "timestamp": _NOW - timedelta(days=1),
        "target_build_sha": "deadbeef",
        "tool": "garak",
        "tool_version": "0.1.0",
        "probe_id": "garak:dan.Dan_11_0",
        "taxonomy": [
            TaxonomyRef(
                framework=(
                    TaxonomyFramework.OWASP_ASI_2026
                    if t.startswith("ASI")
                    else TaxonomyFramework.OWASP_LLM_2026
                ),
                id=t,
            )
            for t in taxonomy_ids
        ],
        "attempts": 10,
        "successes": 5,
        "asr": 0.5,
        "asr_ci_low": 0.24,
        "asr_ci_high": 0.76,
        "seed": 1,
        "evidence_path": None,
        "repro_command": "echo repro",
        "status": FindingStatus.OPEN,
        "control_ref": None,  # before-state findings genuinely have none
        "retest_run_id": None,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _assertions_by_taxonomy() -> dict[str, list]:
    asi01 = record_assertion(_ASI01_CONTROL, [_passing(_ASI01_CONTROL.test_ref)], [], _NOW)
    llm01 = record_assertion(_LLM01_CONTROL, [_passing(_LLM01_CONTROL.test_ref)], [], _NOW)
    return {"ASI01": [asi01], "LLM01:2026": [llm01]}


def test_before_state_finding_with_no_control_ref_still_resolves_via_taxonomy() -> None:
    """Bug 1: a phase_a finding predates the control that later fixed it,
    so it carries control_ref=None — reporting "no control addresses
    this" would be false.
    """
    findings = [_finding("F-1", ["ASI01"])]

    translations = top_business_translations(
        findings, score_all(findings), {}, n=5, assertions_by_taxonomy=_assertions_by_taxonomy()
    )

    assert translations[0].control_ids == ("frozen-plan-execution",)
    assert "Not attributed to any control by Project 1" in translations[0].residual_risk
    # Must not overclaim that the control fixed this specific finding.
    assert "shipped afterwards" not in translations[0].residual_risk


def test_a_finding_tagged_with_two_taxonomies_reports_both_controls() -> None:
    """Bug 2: returning only the first taxonomy's control made the
    reported control an artifact of list order.
    """
    findings = [_finding("F-1", ["ASI01", "LLM01:2026"])]

    translations = top_business_translations(
        findings, score_all(findings), {}, n=5, assertions_by_taxonomy=_assertions_by_taxonomy()
    )

    assert set(translations[0].control_ids) == {
        "frozen-plan-execution",
        "untrusted-context-trust-boundary",
    }


def test_no_matching_control_is_stated_plainly_not_inferred() -> None:
    findings = [_finding("F-1", ["ASI10"])]

    translations = top_business_translations(
        findings, score_all(findings), {}, n=5, assertions_by_taxonomy=_assertions_by_taxonomy()
    )

    assert translations[0].control_ids == ()
    assert "No control in the registry" in translations[0].residual_risk


def test_same_probe_across_runs_is_deduped_to_one_row() -> None:
    findings = [
        _finding("F-1", ["ASI01"], run_id="phase_a_agent_baseline"),
        _finding("F-2", ["ASI01"], run_id="phase_c_agent_baseline"),
        _finding("F-3", ["ASI01"], run_id="phase_c_rag_authorization"),
    ]

    translations = top_business_translations(
        findings, score_all(findings), {}, n=5, assertions_by_taxonomy=_assertions_by_taxonomy()
    )

    assert len(translations) == 1


def test_dedupe_tie_breaks_toward_the_more_recent_run() -> None:
    older = _finding(
        "F-old", ["ASI01"], run_id="phase_a_agent_baseline", timestamp=_NOW - timedelta(days=10)
    )
    newer = _finding(
        "F-new", ["ASI01"], run_id="phase_c_agent_baseline", timestamp=_NOW - timedelta(days=1)
    )
    findings = [older, newer]

    translations = top_business_translations(
        findings, score_all(findings), {}, n=5, assertions_by_taxonomy=_assertions_by_taxonomy()
    )

    assert translations[0].finding_id == "F-new"


def test_a_failing_control_is_reported_as_unmitigated() -> None:
    failing = TestResult(
        test_id=_ASI01_CONTROL.test_ref,
        passed=False,
        timestamp=_NOW,
        duration_s=0.1,
        source="pytest",
    )
    assertion = record_assertion(_ASI01_CONTROL, [failing], [], _NOW)
    findings = [_finding("F-1", ["ASI01"])]

    translations = top_business_translations(
        findings, score_all(findings), {}, n=5, assertions_by_taxonomy={"ASI01": [assertion]}
    )

    assert "treat as unmitigated" in translations[0].residual_risk
