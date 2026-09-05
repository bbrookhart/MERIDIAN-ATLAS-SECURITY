from datetime import UTC, datetime, timedelta

import pytest
from atlas_assurance.evidence_store import evidence_freshness, record_assertion
from atlas_assurance.models import ControlDef, TestResult, UnsupportedClaimError
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef

CONTROL = ControlDef(
    control_id="c1",
    name="Some control",
    description="...",
    control_ref="pkg/module.py::thing",
    test_ref="atlas-control::tests.test_thing::test_it_works",
    max_age_days=30,
    addresses_taxonomy=("LLM03:2026",),
)


def _finding(finding_id: str, control_ref: str | None) -> Finding:
    return Finding(
        finding_id=finding_id,
        run_id="run_x",
        timestamp=datetime.now(UTC),
        target_build_sha="deadbeef",
        tool="atlas-redteam",
        tool_version="0.1.0",
        probe_id="some-probe",
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id="LLM03:2026")],
        attempts=5,
        successes=0,
        asr=0.0,
        asr_ci_low=0.0,
        asr_ci_high=0.1,
        seed=1,
        evidence_path=None,
        repro_command="echo repro",
        status=FindingStatus.MITIGATED,
        control_ref=control_ref,
        retest_run_id=None,
    )


def test_record_assertion_rejects_a_control_with_no_matching_test_result() -> None:
    with pytest.raises(UnsupportedClaimError):
        record_assertion(CONTROL, test_results=[], findings=[])


def test_record_assertion_rejects_when_only_a_differently_named_test_ran() -> None:
    other = TestResult(
        test_id="atlas-control::tests.test_thing::test_something_else",
        passed=True,
        timestamp=datetime.now(UTC),
        duration_s=0.01,
        source="pytest",
    )
    with pytest.raises(UnsupportedClaimError):
        record_assertion(CONTROL, test_results=[other], findings=[])


def test_record_assertion_succeeds_with_a_real_matching_test_result() -> None:
    tr = TestResult(
        test_id=CONTROL.test_ref,
        passed=True,
        timestamp=datetime.now(UTC),
        duration_s=0.01,
        source="pytest",
    )

    assertion = record_assertion(CONTROL, test_results=[tr], findings=[])

    assert assertion.test_result is tr
    assert assertion.finding_ids == ()


def test_record_assertion_links_only_findings_with_a_matching_control_ref() -> None:
    tr = TestResult(
        test_id=CONTROL.test_ref,
        passed=True,
        timestamp=datetime.now(UTC),
        duration_s=0.01,
        source="pytest",
    )
    matching = _finding("F-match", CONTROL.control_ref)
    unrelated = _finding("F-unrelated", "some/other/module.py::other_thing")

    assertion = record_assertion(CONTROL, test_results=[tr], findings=[matching, unrelated])

    assert assertion.finding_ids == ("F-match",)


def test_record_assertion_picks_the_most_recent_of_multiple_matching_results() -> None:
    older = TestResult(
        test_id=CONTROL.test_ref,
        passed=False,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        duration_s=0.01,
        source="pytest",
    )
    newer = TestResult(
        test_id=CONTROL.test_ref,
        passed=True,
        timestamp=datetime(2026, 6, 1, tzinfo=UTC),
        duration_s=0.01,
        source="pytest",
    )

    assertion = record_assertion(CONTROL, test_results=[older, newer], findings=[])

    assert assertion.test_result is newer


def test_evidence_freshness_fresh_within_max_age() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    tr = TestResult(
        test_id=CONTROL.test_ref,
        passed=True,
        timestamp=now - timedelta(days=5),
        duration_s=0.01,
        source="pytest",
    )
    assertion = record_assertion(CONTROL, test_results=[tr], findings=[])

    assert evidence_freshness(assertion, now=now) == "fresh"


def test_evidence_freshness_stale_beyond_max_age() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    tr = TestResult(
        test_id=CONTROL.test_ref,
        passed=True,
        timestamp=now - timedelta(days=31),
        duration_s=0.01,
        source="pytest",
    )
    assertion = record_assertion(CONTROL, test_results=[tr], findings=[])

    assert evidence_freshness(assertion, now=now) == "stale"


def test_evidence_freshness_stale_when_the_latest_result_failed_even_if_recent() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    tr = TestResult(
        test_id=CONTROL.test_ref,
        passed=False,
        timestamp=now - timedelta(hours=1),
        duration_s=0.01,
        source="pytest",
    )
    assertion = record_assertion(CONTROL, test_results=[tr], findings=[])

    assert evidence_freshness(assertion, now=now) == "stale"
