"""Staged commit + rollback window for irreversible actions (issue_refund,
send_email) — so a bad plan can be undone rather than merely regretted.

The action still executes immediately (this isn't a two-phase approval
gate — that's approval.py, for the human-in-the-loop tier above the
`needs_human_signoff` threshold). What staged commit adds is a short
window in which the *effect* can be voided: for `issue_refund`, voiding
means a genuine compensating ledger entry, reversing it. For `send_email`
there is no true undo — the honest limitation is that voiding an email
only records a flag and a required follow-up, since a sent email can't be
unsent. Both are represented the same way rather than pretending
send_email's rollback is as strong as issue_refund's.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from atlas_control.config import settings

STAGED_TOOLS = {"issue_refund", "send_email"}


@dataclass
class StagedAction:
    commit_id: str
    session_id: str
    tool: str
    args: dict
    result: dict
    committed_at: float
    rollback_deadline: float
    status: str = "pending_window"  # -> "finalized" | "voided"


_staged: dict[str, StagedAction] = {}


class RollbackWindowExpiredError(Exception):
    pass


class UnknownStagedActionError(Exception):
    pass


def stage(session_id: str, tool: str, args: dict, result: dict) -> StagedAction:
    now = time.time()
    action = StagedAction(
        commit_id=uuid.uuid4().hex,
        session_id=session_id,
        tool=tool,
        args=args,
        result=result,
        committed_at=now,
        rollback_deadline=now + settings.rollback_window_seconds,
    )
    _staged[action.commit_id] = action
    return action


def get(commit_id: str) -> StagedAction | None:
    return _staged.get(commit_id)


def void(commit_id: str) -> StagedAction:
    action = _staged.get(commit_id)
    if action is None:
        raise UnknownStagedActionError(commit_id)
    if time.time() > action.rollback_deadline:
        raise RollbackWindowExpiredError(
            f"rollback window for {commit_id} closed at {action.rollback_deadline}"
        )
    action.status = "voided"
    return action


def finalize_expired() -> list[StagedAction]:
    """Move any action whose rollback window has passed to "finalized".
    Called opportunistically (e.g. before reading budget/history) rather
    than by a background scheduler, to keep this lab dependency-free.
    """
    now = time.time()
    finalized = []
    for action in _staged.values():
        if action.status == "pending_window" and now > action.rollback_deadline:
            action.status = "finalized"
            finalized.append(action)
    return finalized


def list_for_session(session_id: str) -> list[StagedAction]:
    return [a for a in _staged.values() if a.session_id == session_id]
