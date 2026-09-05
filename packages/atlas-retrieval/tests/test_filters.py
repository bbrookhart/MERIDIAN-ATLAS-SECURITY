from atlas_retrieval.filters import POSTFILTER_CANDIDATES_SQL, PREFILTER_SQL


def test_prefilter_sql_filters_by_allowed_roles_before_ordering():
    assert "WHERE allowed_roles && $1::text[]" in PREFILTER_SQL
    where_idx = PREFILTER_SQL.index("WHERE")
    order_idx = PREFILTER_SQL.index("ORDER BY")
    assert where_idx < order_idx


def test_postfilter_candidates_sql_has_no_role_filter():
    """Post-filter is unfiltered at the SQL layer by design — authorization
    happens after, against the candidate set."""
    assert "WHERE" not in POSTFILTER_CANDIDATES_SQL
    assert "allowed_roles" in POSTFILTER_CANDIDATES_SQL  # selected, not filtered
