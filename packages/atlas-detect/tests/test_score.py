from datetime import UTC, datetime, timedelta

from atlas_detect.score import _score


def test_score_counts_tp_fp_fn_correctly():
    positives = {"attack-1", "attack-2", "attack-3"}
    negatives = {"benign-1", "benign-2"}
    rows = [
        {"SessionId": "attack-1"},  # true positive
        {"SessionId": "benign-1"},  # false positive
        # attack-2, attack-3 never detected -> false negatives
        # benign-2 never detected -> true negative (not counted)
    ]

    result = _score("test-detector", positives, negatives, rows)

    assert result.tp == 1
    assert result.fp == 1
    assert result.fn == 2
    assert result.precision == 0.5  # 1 / (1 + 1)
    assert result.recall == 1 / 3  # 1 / (1 + 2)


def test_score_precision_none_when_nothing_detected():
    result = _score("test-detector", {"a"}, {"b"}, [])
    assert result.tp == 0
    assert result.fp == 0
    assert result.precision is None
    assert result.recall == 0.0  # 0 / (0 + 1)


def test_score_recall_none_when_no_positive_instances():
    """A detector with zero ground-truth positives in this dataset should
    report recall=None (unmeasurable), not a misleading 0.0 or 1.0."""
    result = _score("test-detector", set(), {"b"}, [])
    assert result.recall is None


def test_score_computes_mttd_from_matched_rows():
    old_ts = datetime.now(UTC) - timedelta(seconds=30)
    rows = [{"SessionId": "attack-1", "Timestamp": old_ts}]

    result = _score("test-detector", {"attack-1"}, set(), rows)

    assert result.mttd_seconds is not None
    assert 29 <= result.mttd_seconds <= 32


def test_score_mttd_none_when_no_timestamp_field():
    rows = [{"SessionId": "attack-1"}]
    result = _score("test-detector", {"attack-1"}, set(), rows)
    assert result.mttd_seconds is None
