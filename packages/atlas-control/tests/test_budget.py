from atlas_control import budget


def test_budget_starts_at_zero():
    budget.reset("budget-test")
    snap = budget.snapshot("budget-test")
    assert snap.tool_calls_used == 0
    assert snap.refund_cents_used == 0


def test_record_tool_call_increments_count():
    budget.reset("budget-test-2")
    budget.record_tool_call("budget-test-2", "search_kb", {"query": "x"})
    budget.record_tool_call("budget-test-2", "lookup_claim", {"claim_number": "CLM-1"})
    snap = budget.snapshot("budget-test-2")
    assert snap.tool_calls_used == 2
    assert snap.refund_cents_used == 0


def test_record_tool_call_accumulates_refund_amount():
    budget.reset("budget-test-3")
    budget.record_tool_call(
        "budget-test-3", "issue_refund", {"claim_number": "CLM-1", "amount_cents": 20000}
    )
    budget.record_tool_call(
        "budget-test-3", "issue_refund", {"claim_number": "CLM-2", "amount_cents": 15000}
    )
    snap = budget.snapshot("budget-test-3")
    assert snap.tool_calls_used == 2
    assert snap.refund_cents_used == 35000
