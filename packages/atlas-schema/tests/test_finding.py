from datetime import UTC, datetime

import pytest
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef
from pydantic import ValidationError


def make_finding(**overrides):
    base = {
        "finding_id": "F-1",
        "run_id": "run-1",
        "timestamp": datetime(2026, 8, 9, tzinfo=UTC),
        "target_build_sha": "a" * 40,
        "tool": "atlas-redteam",
        "tool_version": "0.1.0",
        "probe_id": "probe-1",
        "taxonomy": [TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id="LLM01")],
        "attempts": 10,
        "successes": 5,
        "asr": 0.5,
        "asr_ci_low": 0.3,
        "asr_ci_high": 0.7,
        "seed": 1,
        "evidence_path": None,
        "repro_command": "atlas-redteam run --probe probe-1",
        "status": FindingStatus.OPEN,
        "control_ref": None,
        "retest_run_id": None,
    }
    base.update(overrides)
    return Finding(**base)


def test_valid_finding_round_trips():
    finding = make_finding()
    assert finding.attempts == 10
    assert finding.successes == 5


def test_successes_cannot_exceed_attempts():
    with pytest.raises(ValidationError):
        make_finding(attempts=5, successes=6)


def test_successes_cannot_be_negative():
    with pytest.raises(ValidationError):
        make_finding(successes=-1)


def test_asr_must_be_within_ci_bounds():
    with pytest.raises(ValidationError):
        make_finding(asr=0.9, asr_ci_low=0.3, asr_ci_high=0.7)


def test_asr_at_ci_bounds_is_valid():
    finding = make_finding(asr=0.3, asr_ci_low=0.3, asr_ci_high=0.7)
    assert finding.asr == 0.3
    finding = make_finding(asr=0.7, asr_ci_low=0.3, asr_ci_high=0.7)
    assert finding.asr == 0.7


@pytest.mark.parametrize(
    "asr,asr_ci_low,asr_ci_high,expected",
    [
        (0.96, 0.94, 0.98, "deterministic"),
        (1.0, 0.99, 1.0, "deterministic"),
        (0.04, 0.0, 0.25, "flaky"),
        (0.0, 0.0, 0.3, "flaky"),
        (0.5, 0.4, 0.6, "probabilistic"),
        (0.95, 0.9, 0.99, "probabilistic"),
        (0.04, 0.0, 0.2, "probabilistic"),
        (0.05, 0.0, 0.3, "probabilistic"),
    ],
)
def test_determinism_class_boundaries(asr, asr_ci_low, asr_ci_high, expected):
    finding = make_finding(asr=asr, asr_ci_low=asr_ci_low, asr_ci_high=asr_ci_high)
    assert finding.determinism_class == expected
