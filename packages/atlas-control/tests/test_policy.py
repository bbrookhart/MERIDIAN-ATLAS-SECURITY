"""Real opa eval calls (the opa binary, no mocking) — fast and
deterministic, so there's no reason to fake the policy engine in tests.
"""

from atlas_control.policy import AuthorizationRequest, authorize


def _req(**overrides) -> AuthorizationRequest:
    base = {
        "role": "adjuster",
        "session_id": "s1",
        "tool": "issue_refund",
        "args": {"claim_number": "CLM-1", "amount_cents": 40000},
        "tool_calls_used": 0,
        "refund_cents_used": 0,
    }
    base.update(overrides)
    return AuthorizationRequest(**base)


def test_refund_within_threshold_is_allowed():
    result = authorize(_req())
    assert result.allow
    assert result.reason == "allowed"


def test_refund_over_threshold_is_denied():
    result = authorize(_req(args={"claim_number": "CLM-1", "amount_cents": 5000000}))
    assert not result.allow
    assert result.reason == "refund exceeds policy threshold"


def test_broker_cannot_issue_refund():
    result = authorize(_req(role="broker", args={"claim_number": "CLM-1", "amount_cents": 10000}))
    assert not result.allow
    assert result.reason == "tool not permitted for role"


def test_hr_can_search_kb_but_not_lookup_claim():
    allowed = authorize(_req(role="hr", tool="search_kb", args={"query": "x"}))
    denied = authorize(_req(role="hr", tool="lookup_claim", args={"claim_number": "CLM-1"}))
    assert allowed.allow
    assert not denied.allow


def test_session_budget_exhausted():
    result = authorize(_req(tool="search_kb", args={"query": "x"}, tool_calls_used=20))
    assert not result.allow
    assert result.reason == "session budget exceeded"


def test_string_valued_amount_cents_is_normalized_not_denied_by_type():
    """Regression guard for a real bug found live via Project 4's benign
    traffic generator: OPA's comparison operators use a total type
    ordering where any string sorts as greater than any number
    (`opa eval '"50" > 50000'` -> true), so a well-under-threshold refund
    whose amount arrived as a JSON string (Ollama formats tool-call
    arguments inconsistently) was being denied as "over threshold"
    regardless of the actual amount. _normalize_args() must coerce it to
    a real int before it reaches OPA."""
    result = authorize(_req(args={"claim_number": "CLM-1", "amount_cents": "5000"}))
    assert result.allow
    assert result.reason == "allowed"


def test_string_valued_amount_cents_over_threshold_is_still_denied():
    """The normalization must not accidentally defeat the real threshold
    check for a genuinely over-threshold amount that happens to arrive as
    a string."""
    result = authorize(_req(args={"claim_number": "CLM-1", "amount_cents": "5000000"}))
    assert not result.allow
    assert result.reason == "refund exceeds policy threshold"
