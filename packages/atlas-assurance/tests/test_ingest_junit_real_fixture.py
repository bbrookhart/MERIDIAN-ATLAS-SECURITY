"""Parses a genuinely generated `pytest --junitxml` file (not hand-typed) —
produced once by running atlas-control's real suite and committed as a
fixture, per the plan's own instruction to prove this parser against
real output.
"""

from pathlib import Path

from atlas_assurance.ingest.junit import parse_junit

FIXTURE = Path(__file__).parent / "fixtures" / "atlas_control_junit_real.xml"


def test_parses_all_43_real_atlas_control_tests() -> None:
    results = parse_junit(FIXTURE, package="atlas-control")

    assert len(results) == 43
    assert all(r.passed for r in results)


def test_a_known_real_test_id_is_present() -> None:
    results = parse_junit(FIXTURE, package="atlas-control")

    test_ids = {r.test_id for r in results}
    assert (
        "atlas-control::tests.test_policy::test_refund_over_threshold_is_denied_regardless_of_framing"
        not in test_ids  # that's the opa test name, not the pytest one — guards against confusing the two
    )
    assert "atlas-control::tests.test_policy::test_refund_over_threshold_is_denied" in test_ids
