"""Per-session blast-radius budgets (ASI08 — Cascading Agent Failures).

In-memory for this lab-scale, single-process service — a production
deployment would back this with the same durable store as capability
token redemption tracking. Counts feed into policy.authorize()'s input so
the budget check is enforced by the same policy engine as everything else,
not by a separate ad-hoc guard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionBudget:
    tool_calls_used: int = 0
    refund_cents_used: int = 0


_budgets: dict[str, SessionBudget] = {}


def get(session_id: str) -> SessionBudget:
    return _budgets.setdefault(session_id, SessionBudget())


def record_tool_call(session_id: str, tool: str, args: dict) -> None:
    budget = get(session_id)
    budget.tool_calls_used += 1
    if tool == "issue_refund":
        budget.refund_cents_used += int(args.get("amount_cents", 0))


def reset(session_id: str) -> None:
    """Test/dev helper — a real deployment would expire budgets by TTL."""
    _budgets.pop(session_id, None)


@dataclass(frozen=True)
class BudgetSnapshot:
    session_id: str
    tool_calls_used: int
    refund_cents_used: int


def snapshot(session_id: str) -> BudgetSnapshot:
    b = get(session_id)
    return BudgetSnapshot(session_id, b.tool_calls_used, b.refund_cents_used)
