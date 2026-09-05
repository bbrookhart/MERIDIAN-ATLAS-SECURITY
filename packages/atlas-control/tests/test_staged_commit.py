import pytest
from atlas_control import staged_commit


def test_stage_creates_pending_action():
    action = staged_commit.stage("s1", "issue_refund", {"amount_cents": 40000}, {"issued": True})
    assert action.status == "pending_window"
    assert staged_commit.get(action.commit_id) is action


def test_void_within_window_succeeds():
    action = staged_commit.stage("s1", "issue_refund", {"amount_cents": 40000}, {"issued": True})
    voided = staged_commit.void(action.commit_id)
    assert voided.status == "voided"


def test_void_unknown_commit_id_raises():
    with pytest.raises(staged_commit.UnknownStagedActionError):
        staged_commit.void("no-such-commit")


def test_void_after_window_expired_raises():
    action = staged_commit.stage("s1", "send_email", {"to": "x@example.com"}, {"sent": True})
    action.rollback_deadline = 0  # simulate an already-expired window
    with pytest.raises(staged_commit.RollbackWindowExpiredError):
        staged_commit.void(action.commit_id)


def test_finalize_expired_moves_status():
    action = staged_commit.stage("s1", "issue_refund", {"amount_cents": 1000}, {"issued": True})
    action.rollback_deadline = 0
    finalized = staged_commit.finalize_expired()
    assert action in finalized
    assert action.status == "finalized"


def test_list_for_session_filters_correctly():
    staged_commit.stage("session-a", "issue_refund", {"amount_cents": 1000}, {"issued": True})
    staged_commit.stage("session-b", "issue_refund", {"amount_cents": 2000}, {"issued": True})
    results = staged_commit.list_for_session("session-a")
    assert all(a.session_id == "session-a" for a in results)
    assert len(results) >= 1
