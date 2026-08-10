"""Plan-then-execute: the structural defense against ASI01 (Agent Goal
Hijack).

A plan is a list of {tool, args} steps, validated against policy and hashed
*before* any of them run. Execution only ever happens through
`execute_step(plan_id, step_index)` — there is no API to invoke an arbitrary
tool with arbitrary arguments. Content encountered mid-execution (a tool
result, a retrieved document, an MCP response) cannot introduce a new step:
the caller can only ask to execute the next already-frozen, already-approved
index. An out-of-range index, an already-executed index, or a denied index
is a deviation attempt — rejected and logged as a security event, not
silently run and not treated as an ordinary error either.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field

import asyncpg
import httpx
from opentelemetry import trace

from atlas_control import budget, capability, policy


@dataclass(frozen=True)
class PlanStep:
    tool: str
    args: dict


@dataclass(frozen=True)
class StepDecision:
    approved: bool
    reason: str


@dataclass
class Plan:
    plan_id: str
    session_id: str
    role: str
    steps: tuple[PlanStep, ...]
    decisions: tuple[StepDecision, ...]
    plan_hash: str
    created_at: float = field(default_factory=time.time)
    executed: list[bool] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.executed:
            self.executed = [False] * len(self.steps)


class PlanDeviationError(Exception):
    pass


@dataclass(frozen=True)
class DeviationEvent:
    plan_id: str
    reason: str
    step_index: int | None


_plans: dict[str, Plan] = {}
_deviation_log: list[DeviationEvent] = []


def deviation_events() -> list[DeviationEvent]:
    return list(_deviation_log)


def _log_deviation(plan_id: str, reason: str, step_index: int | None) -> None:
    """Records the deviation both in-process (`deviation_events()`, used
    directly by tests and by anything running in the same Python process)
    and as a span event on whatever span is active when it happens — which,
    in the live service, is the FastAPI-auto-instrumented server span for
    the `/plan/{plan_id}/steps/{step_index}/execute` request (see
    `atlas_control/app.py`). That's what makes this a detectable event in
    the trace store, not just a Python-process-local list — the Project 4
    plan-deviation detector reads it from there, replaying against real
    exported spans rather than reaching into this module's memory."""
    _deviation_log.append(DeviationEvent(plan_id, reason, step_index))
    span = trace.get_current_span()
    span.add_event(
        "atlas.plan.deviation",
        attributes={"plan_id": plan_id, "reason": reason, "step_index": step_index or -1},
    )


def _hash_steps(steps: list[PlanStep]) -> str:
    canonical = json.dumps(
        [{"tool": s.tool, "args": s.args} for s in steps], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def submit_plan(session_id: str, role: str, raw_steps: list[dict]) -> Plan:
    """Validate each step against policy, accounting for the *cumulative*
    effect of earlier steps in this same plan (so a plan can't split one
    over-threshold refund into several under-threshold ones), then hash and
    freeze the whole plan. This is the only place a Plan is created.
    """
    steps = tuple(PlanStep(tool=s["tool"], args=s.get("args", {})) for s in raw_steps)

    running_tool_calls = budget.get(session_id).tool_calls_used
    running_refund_cents = budget.get(session_id).refund_cents_used

    decisions: list[StepDecision] = []
    for step in steps:
        req = policy.AuthorizationRequest(
            role=role,
            session_id=session_id,
            tool=step.tool,
            args=step.args,
            tool_calls_used=running_tool_calls,
            refund_cents_used=running_refund_cents,
        )
        result = policy.authorize(req)
        decisions.append(StepDecision(approved=result.allow, reason=result.reason))
        if result.allow:
            running_tool_calls += 1
            if step.tool == "issue_refund":
                running_refund_cents += int(step.args.get("amount_cents", 0))

    plan_id = uuid.uuid4().hex
    plan = Plan(
        plan_id=plan_id,
        session_id=session_id,
        role=role,
        steps=steps,
        decisions=tuple(decisions),
        plan_hash=_hash_steps(list(steps)),
    )
    _plans[plan_id] = plan
    return plan


def get_plan(plan_id: str) -> Plan | None:
    return _plans.get(plan_id)


async def execute_step(
    plan_id: str, step_index: int, pool: asyncpg.Pool, http_client: httpx.AsyncClient
) -> tuple[PlanStep, str]:
    """Execute exactly one already-approved, not-yet-executed step from an
    already-frozen plan. Returns (the step, its JSON result string).

    Any call that doesn't correspond to a legitimate next step on a real
    plan is a deviation: logged to `_deviation_log`, raised as
    PlanDeviationError, never silently executed.

    `pool`/`http_client` are passed in by the router (from app.state) rather
    than looked up globally here, so this module has no hidden dependency
    on the FastAPI app being constructed — it's directly unit-testable.
    """
    from atlas_control import dispatch  # local import avoids a cycle with app wiring

    plan = _plans.get(plan_id)
    if plan is None:
        _log_deviation(plan_id, "unknown plan_id", step_index)
        raise PlanDeviationError(f"unknown plan_id {plan_id!r}")

    if not (0 <= step_index < len(plan.steps)):
        _log_deviation(plan_id, "step_index out of range", step_index)
        raise PlanDeviationError(f"step_index {step_index} out of range for plan {plan_id!r}")

    if plan.executed[step_index]:
        _log_deviation(plan_id, "step already executed", step_index)
        raise PlanDeviationError(f"step {step_index} of plan {plan_id!r} already executed")

    decision = plan.decisions[step_index]
    if not decision.approved:
        _log_deviation(plan_id, f"step denied by policy: {decision.reason}", step_index)
        raise PlanDeviationError(f"step {step_index} was denied by policy: {decision.reason}")

    step = plan.steps[step_index]

    token = capability.mint(step.tool, step.args, plan.session_id)
    capability.redeem(token, step.tool, step.args, plan.session_id)

    _tools, mcp_routes = await dispatch.available_tools()
    result = await dispatch.dispatch(step.tool, step.args, pool, http_client, plan.role, mcp_routes)

    plan.executed[step_index] = True
    budget.record_tool_call(plan.session_id, step.tool, step.args)

    return step, result
