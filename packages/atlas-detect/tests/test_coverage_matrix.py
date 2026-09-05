from atlas_detect.coverage import ASI_IDS, LLM_IDS, build_matrix
from atlas_detect.score import DetectorScore, ScoreReport


def test_matrix_covers_every_taxonomy_id():
    report = ScoreReport(scores=[], unmeasurable={})
    matrix = build_matrix(report)
    for tid in LLM_IDS + ASI_IDS:
        assert tid in matrix


def test_uncovered_taxonomy_has_a_stated_reason_not_a_blank():
    report = ScoreReport(scores=[], unmeasurable={})
    matrix = build_matrix(report)
    for tid, entry in matrix.items():
        if not entry["detectors"]:
            assert entry["uncovered_reason"], f"{tid} has no detector and no stated reason"


def test_mapped_taxonomy_gets_measured_recall():
    report = ScoreReport(
        scores=[
            DetectorScore(
                name="retrieval_violation",
                tp=1,
                fp=0,
                fn=0,
                precision=1.0,
                recall=1.0,
                mttd_seconds=None,
            )
        ],
        unmeasurable={},
    )
    matrix = build_matrix(report)
    entry = matrix["LLM02:2026"]
    assert "retrieval_violation" in entry["detectors"]
    assert entry["recall"]["retrieval_violation"] == 1.0


def test_asi01_maps_to_plan_deviation_and_tool_sequence_anomaly():
    report = ScoreReport(scores=[], unmeasurable={})
    matrix = build_matrix(report)
    assert set(matrix["ASI01"]["detectors"]) == {"plan_deviation", "tool_sequence_anomaly"}
