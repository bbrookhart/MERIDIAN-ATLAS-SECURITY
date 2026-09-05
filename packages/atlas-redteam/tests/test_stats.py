import pytest
from atlas_redteam.stats import classify, wilson_interval


def test_wilson_interval_known_values():
    # 39/40 successes, 95% Wilson interval — reference values computed
    # independently from the closed-form formula.
    result = wilson_interval(39, 40)
    assert result.asr == pytest.approx(0.975, abs=1e-6)
    assert result.ci_low == pytest.approx(0.8712, abs=1e-3)
    assert result.ci_high == pytest.approx(0.9956, abs=1e-3)
    assert result.ci_low < result.asr < result.ci_high


def test_wilson_interval_zero_successes():
    result = wilson_interval(0, 10)
    assert result.asr == 0.0
    assert result.ci_low == 0.0
    assert result.ci_high > 0.0


def test_wilson_interval_all_successes():
    result = wilson_interval(10, 10)
    assert result.asr == pytest.approx(1.0)
    assert result.ci_high == pytest.approx(1.0)
    assert result.ci_low < 1.0


def test_wilson_interval_rejects_invalid_input():
    with pytest.raises(ValueError):
        wilson_interval(5, 0)
    with pytest.raises(ValueError):
        wilson_interval(-1, 10)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


@pytest.mark.parametrize(
    "asr,ci_low,ci_high,expected",
    [
        (0.96, 0.94, 0.98, "deterministic"),
        (1.0, 0.99, 1.0, "deterministic"),
        (0.04, 0.0, 0.25, "flaky"),
        (0.0, 0.0, 0.3, "flaky"),
        (0.5, 0.4, 0.6, "probabilistic"),
        (0.95, 0.9, 0.99, "probabilistic"),
        (0.04, 0.0, 0.2, "probabilistic"),
    ],
)
def test_classify_matches_finding_determinism_class(asr, ci_low, ci_high, expected):
    assert classify(asr, ci_low, ci_high) == expected
