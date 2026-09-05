from atlas_assurance.executive_summary import _diff_since, render_executive_summary

_BASE_REGISTER = {
    "generated_at": "2026-01-01T00:00:00+00:00",
    "controls_assessed": 2,
    "controls_not_assessed": 0,
    "controls_stale": 0,
    "controls": [
        {"control_id": "c1", "status": "assessed", "freshness": "fresh"},
        {"control_id": "c2", "status": "assessed", "freshness": "fresh"},
    ],
    "coverage_gaps": [{"taxonomy_id": "LLM01:2026", "name": "Prompt Injection", "reason": "x"}],
    "business_translation_top5": [
        {
            "finding_id": "F-1",
            "aivss_score": 3.0,
            "technical_finding": "some probe (tool) - open",
            "attacker_achieves": "does a bad thing",
            "business_impact_insurer": "costs money",
            "control_ids": (),
            "control_names": (),
            "residual_risk": "full",
        }
    ],
}


def test_render_executive_summary_is_valid_looking_html() -> None:
    output = render_executive_summary(_BASE_REGISTER)

    assert output.startswith("<!doctype html>")
    assert "Top 3 residual risks" in output
    assert "First generated report" in output


def test_diff_since_reports_no_changes_for_identical_registers() -> None:
    changes = _diff_since(_BASE_REGISTER, _BASE_REGISTER)

    assert changes == [
        "No control status, freshness, or coverage-gap changes since the last report."
    ]


def test_diff_since_detects_a_status_change() -> None:
    old = _BASE_REGISTER
    new = {
        **_BASE_REGISTER,
        "controls": [
            {"control_id": "c1", "status": "not_assessed", "freshness": None},
            {"control_id": "c2", "status": "assessed", "freshness": "fresh"},
        ],
    }

    changes = _diff_since(new, old)

    assert any("c1: status assessed → not_assessed" in c for c in changes)


def test_diff_since_detects_a_new_coverage_gap() -> None:
    old = _BASE_REGISTER
    new = {
        **_BASE_REGISTER,
        "coverage_gaps": [
            *_BASE_REGISTER["coverage_gaps"],
            {"taxonomy_id": "ASI01", "name": "Agent Goal Hijack", "reason": "y"},
        ],
    }

    changes = _diff_since(new, old)

    assert any("new coverage gap: ASI01" in c for c in changes)


def test_render_executive_summary_with_previous_register_shows_real_diff() -> None:
    new = {
        **_BASE_REGISTER,
        "controls": [
            {"control_id": "c1", "status": "not_assessed", "freshness": None},
            {"control_id": "c2", "status": "assessed", "freshness": "fresh"},
        ],
    }

    output = render_executive_summary(new, previous_register=_BASE_REGISTER)

    assert "status assessed" in output
