import pytest
from atlas_control import budget, plan


@pytest.fixture(autouse=True)
def _reset_budget():
    budget.reset("plan-test-session")
    yield
    budget.reset("plan-test-session")


def test_submit_plan_approves_within_policy_step():
    p = plan.submit_plan(
        "plan-test-session",
        "adjuster",
        [{"tool": "lookup_claim", "args": {"claim_number": "CLM-1"}}],
    )
    assert p.decisions[0].approved
    assert len(p.plan_hash) == 64  # sha256 hex


def test_submit_plan_denies_over_threshold_step():
    p = plan.submit_plan(
        "plan-test-session",
        "adjuster",
        [{"tool": "issue_refund", "args": {"claim_number": "CLM-1", "amount_cents": 5000000}}],
    )
    assert not p.decisions[0].approved
    assert p.decisions[0].reason == "refund exceeds policy threshold"


def test_submit_plan_catches_split_refund_within_one_plan():
    """Two refunds that are each individually under threshold but exceed
    the session's cumulative refund budget together — the second step must
    be denied even though it looks fine in isolation.
    """
    p = plan.submit_plan(
        "plan-test-session",
        "adjuster",
        [
            {"tool": "issue_refund", "args": {"claim_number": "CLM-1", "amount_cents": 40000}},
            {"tool": "issue_refund", "args": {"claim_number": "CLM-2", "amount_cents": 40000}},
        ],
    )
    assert p.decisions[0].approved
    assert not p.decisions[1].approved
    assert p.decisions[1].reason == "session budget exceeded"


def test_plan_hash_is_deterministic_for_same_steps():
    steps = [{"tool": "search_kb", "args": {"query": "x"}}]
    p1 = plan.submit_plan("plan-test-session", "adjuster", steps)
    p2 = plan.submit_plan("plan-test-session", "adjuster", steps)
    assert p1.plan_hash == p2.plan_hash


async def test_execute_step_rejects_denied_step():
    p = plan.submit_plan(
        "plan-test-session",
        "adjuster",
        [{"tool": "issue_refund", "args": {"claim_number": "CLM-1", "amount_cents": 5000000}}],
    )
    with pytest.raises(plan.PlanDeviationError):
        await plan.execute_step(p.plan_id, 0, None, None)


async def test_execute_step_rejects_out_of_range_index():
    p = plan.submit_plan(
        "plan-test-session", "adjuster", [{"tool": "search_kb", "args": {"query": "x"}}]
    )
    with pytest.raises(plan.PlanDeviationError):
        await plan.execute_step(p.plan_id, 5, None, None)


async def test_execute_step_rejects_unknown_plan_id():
    with pytest.raises(plan.PlanDeviationError):
        await plan.execute_step("does-not-exist", 0, None, None)


async def test_deviation_attempts_are_logged():
    before = len(plan.deviation_events())
    with pytest.raises(plan.PlanDeviationError):
        await plan.execute_step("does-not-exist-either", 0, None, None)
    after = len(plan.deviation_events())
    assert after == before + 1
