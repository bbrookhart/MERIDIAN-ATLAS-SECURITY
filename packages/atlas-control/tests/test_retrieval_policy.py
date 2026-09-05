"""Real opa eval calls against retrieval_authorization.rego — same
philosophy as test_policy.py: fast, deterministic, no reason to mock the
policy engine.
"""

from atlas_control.retrieval_policy import authorize_retrieval


def test_broker_visible_roles_exclude_hr():
    result = authorize_retrieval("broker")
    assert set(result.visible_roles) == {"broker", "shared"}


def test_hr_visible_roles_are_hr_only():
    result = authorize_retrieval("hr")
    assert set(result.visible_roles) == {"hr"}


def test_unknown_role_gets_no_visibility():
    result = authorize_retrieval("vendor")
    assert result.visible_roles == []


def test_postfilter_denies_hr_chunk_for_broker():
    result = authorize_retrieval("broker", [{"chunk_id": 2, "allowed_roles": ["hr"]}])
    assert result.decisions == [
        {"chunk_id": 2, "allowed_roles": ["hr"], "allow": False, "rule": "role_not_permitted"}
    ]


def test_postfilter_allows_shared_chunk_for_adjuster():
    result = authorize_retrieval(
        "adjuster", [{"chunk_id": 3, "allowed_roles": ["broker", "adjuster"]}]
    )
    assert result.decisions[0]["allow"] is True


def test_postfilter_preserves_one_decision_per_submitted_chunk():
    """Regression guard: chunk_allowed must be a total function. A partial
    rule silently drops denied chunks from the output array instead of
    reporting allow=false — caught live during Project 2 development."""
    chunks = [
        {"chunk_id": 1, "allowed_roles": ["adjuster"]},
        {"chunk_id": 2, "allowed_roles": ["hr"]},
        {"chunk_id": 3, "allowed_roles": ["broker", "adjuster"]},
    ]
    result = authorize_retrieval("adjuster", chunks)
    assert len(result.decisions) == 3
    assert {d["chunk_id"]: d["allow"] for d in result.decisions} == {1: True, 2: False, 3: True}
