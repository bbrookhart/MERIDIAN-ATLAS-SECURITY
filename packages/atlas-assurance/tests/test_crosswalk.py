from atlas_assurance.crosswalk import crosswalk_for, full_crosswalk
from atlas_assurance.models import Framework
from atlas_assurance.registry import CONTROLS, crosswalk_refs_for_control
from atlas_schema.taxonomy import ALL_CATEGORIES


def test_crosswalk_for_unknown_id_returns_empty() -> None:
    assert crosswalk_for("NOT-A-REAL-ID") == []


def test_crosswalk_for_a_real_id_covers_all_six_frameworks() -> None:
    refs = crosswalk_for("LLM01:2026")

    frameworks = {r.framework for r in refs}
    assert frameworks == set(Framework)


def test_full_crosswalk_covers_every_taxonomy_id() -> None:
    matrix = full_crosswalk()

    assert set(matrix.keys()) == set(ALL_CATEGORIES.keys())
    assert all(len(refs) == 6 for refs in matrix.values())


def test_every_registry_control_resolves_to_at_least_one_framework_ref() -> None:
    for control in CONTROLS:
        refs = crosswalk_refs_for_control(control)
        assert len(refs) > 0, control.control_id
