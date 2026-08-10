from atlas_redteam.coverage import build_coverage_matrix


def test_coverage_matrix_includes_all_20_categories():
    matrix = build_coverage_matrix({})
    assert len(matrix) == 20
    ids = {row.taxonomy_id for row in matrix}
    assert "LLM01:2026" in ids
    assert "ASI10" in ids


def test_coverage_matrix_marks_reached_categories():
    matrix = build_coverage_matrix({"garak:latentinjection.Foo": ["LLM01:2026"]})
    row = next(r for r in matrix if r.taxonomy_id == "LLM01:2026")
    assert row.covered
    assert "garak:latentinjection.Foo" in row.probe_ids


def test_coverage_matrix_flags_human_judgment_categories():
    matrix = build_coverage_matrix({})
    llm02 = next(r for r in matrix if r.taxonomy_id == "LLM02:2026")
    llm07 = next(r for r in matrix if r.taxonomy_id == "LLM07:2026")
    llm01 = next(r for r in matrix if r.taxonomy_id == "LLM01:2026")
    assert llm02.needs_human_judgment
    assert llm07.needs_human_judgment
    assert not llm01.needs_human_judgment
