from pathlib import Path

from atlas_assurance.ingest.junit import parse_junit

REAL_JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="1" skipped="1" tests="3" time="1.104" timestamp="2026-08-10T15:29:25.313211-05:00" hostname="host"><testcase classname="tests.test_policy" name="test_refund_within_threshold_is_allowed" time="0.015" /><testcase classname="tests.test_policy" name="test_broken_thing" time="0.002"><failure message="assert False">AssertionError</failure></testcase><testcase classname="tests.test_policy" name="test_skipped_thing" time="0.000"><skipped message="skip" /></testcase></testsuite></testsuites>"""


def test_parses_real_junit_output_shape(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text(REAL_JUNIT_XML)

    results = parse_junit(path, package="atlas-control")

    assert len(results) == 2  # skipped test dropped
    passed = {r.test_id: r.passed for r in results}
    assert (
        passed["atlas-control::tests.test_policy::test_refund_within_threshold_is_allowed"] is True
    )
    assert passed["atlas-control::tests.test_policy::test_broken_thing"] is False


def test_every_result_carries_the_suite_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text(REAL_JUNIT_XML)

    results = parse_junit(path, package="atlas-control")

    assert len({r.timestamp for r in results}) == 1
    assert results[0].timestamp.isoformat() == "2026-08-10T15:29:25.313211-05:00"


def test_source_is_always_pytest(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text(REAL_JUNIT_XML)

    results = parse_junit(path, package="atlas-control")

    assert all(r.source == "pytest" for r in results)
