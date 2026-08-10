"""Append-only evidence store and the no-unsupported-claims enforcement.

This is the one module the master prompt's constraint section is about:
*"No assertion may exist without a linked artifact. Enforce this in
code — the pipeline should fail rather than emit an unsupported claim."*

`record_assertion` is the only way to produce a `ControlAssertion`. It
raises `UnsupportedClaimError` — it does not return a "degraded" or
"partial" assertion — when the control's declared `test_ref` has no
matching, real `TestResult` in what was actually ingested. Callers
(`register.py`) are expected to catch that and record the control as
`"not_assessed"`, per the constraint that absent evidence must be stated
as absent, never inferred.

A referenced `Finding` is trusted only if it was actually loaded from
`evidence/findings.duckdb` — `record_assertion` never accepts a bare
string finding_id, only real `Finding` objects, so a fabricated ID simply
can't be linked in the first place.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atlas_schema import Finding

from atlas_assurance.models import (
    ControlAssertion,
    ControlDef,
    Freshness,
    TestResult,
    UnsupportedClaimError,
)


def record_assertion(
    control: ControlDef,
    test_results: list[TestResult],
    findings: list[Finding],
    generated_at: datetime | None = None,
) -> ControlAssertion:
    generated_at = generated_at or datetime.now(UTC)

    matches = [t for t in test_results if t.test_id == control.test_ref]
    if not matches:
        raise UnsupportedClaimError(
            f"control {control.control_id!r} declares test_ref={control.test_ref!r}, "
            "but no matching TestResult was ingested — refusing to assert it is effective"
        )
    test_result = max(matches, key=lambda t: t.timestamp)

    linked_finding_ids = tuple(
        sorted({f.finding_id for f in findings if f.control_ref == control.control_ref})
    )

    return ControlAssertion(
        control=control,
        test_result=test_result,
        finding_ids=linked_finding_ids,
        generated_at=generated_at,
    )


def evidence_freshness(assertion: ControlAssertion, now: datetime | None = None) -> Freshness:
    """ "stale" covers two distinct real conditions folded into one status
    for reporting simplicity: evidence older than the control's max_age,
    and evidence whose last known result was a failure (a failing test is
    never valid proof of an effective control, no matter how recent). The
    underlying `test_result.passed` stays visible on the assertion for
    anything that needs to tell the two apart.
    """
    now = now or datetime.now(UTC)
    if not assertion.test_result.passed:
        return "stale"
    age = now - assertion.test_result.timestamp
    return "fresh" if age <= timedelta(days=assertion.control.max_age_days) else "stale"
