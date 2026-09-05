"""Parses real `pytest --junitxml=...` output.

pytest's JUnit XML carries one timestamp per *suite*, not per test case —
confirmed against a real run of atlas-control's own suite. Every test in
a suite is therefore stamped with that suite's timestamp; this is the
honest granularity the format actually provides, not a per-test value we
don't have. Skipped tests carry no pass/fail signal and are dropped.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from atlas_assurance.models import TestResult


def parse_junit(path: Path, package: str) -> list[TestResult]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))

    results: list[TestResult] = []
    for suite in suites:
        timestamp = datetime.fromisoformat(suite.attrib["timestamp"])
        for testcase in suite.findall("testcase"):
            if testcase.find("skipped") is not None:
                continue
            failed = testcase.find("failure") is not None or testcase.find("error") is not None
            classname = testcase.attrib.get("classname", "")
            name = testcase.attrib["name"]
            results.append(
                TestResult(
                    test_id=f"{package}::{classname}::{name}",
                    passed=not failed,
                    timestamp=timestamp,
                    duration_s=float(testcase.attrib.get("time", 0.0)),
                    source="pytest",
                )
            )
    return results
