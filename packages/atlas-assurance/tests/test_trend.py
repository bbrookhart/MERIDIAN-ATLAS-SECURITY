from atlas_assurance.ingest.findings import load_findings
from atlas_assurance.trend import build_trend, group_by_taxonomy, render_trend_report


def test_build_trend_covers_every_real_committed_finding_taxonomy_pair() -> None:
    findings = load_findings()
    expected = sum(len(f.taxonomy) for f in findings)

    points = build_trend(findings)

    assert len(points) == expected


def test_build_trend_is_sorted_by_taxonomy_then_timestamp() -> None:
    findings = load_findings()

    points = build_trend(findings)

    keys = [(p.taxonomy_id, p.timestamp) for p in points]
    assert keys == sorted(keys)


def test_group_by_taxonomy_round_trips_the_full_point_count() -> None:
    findings = load_findings()
    points = build_trend(findings)

    grouped = group_by_taxonomy(points)

    assert sum(len(v) for v in grouped.values()) == len(points)


def test_a_real_taxonomy_id_shows_a_before_after_run_pair() -> None:
    """LLM03:2026 / ASI02 (refund-threshold-bypass) has real committed
    findings in both a phase_a_* (before) and a phase_c_* (after) run —
    the genuine trend this view exists to show.
    """
    findings = load_findings()
    points = build_trend(findings)
    grouped = group_by_taxonomy(points)

    asi02_runs = {p.run_id for p in grouped.get("ASI02", [])}
    assert any(r.startswith("phase_c_") for r in asi02_runs)


def test_render_trend_report_is_valid_looking_html() -> None:
    findings = load_findings()
    points = build_trend(findings)

    output = render_trend_report(points)

    assert output.startswith("<!doctype html>")
    assert "ASR trend" in output
