import pytest
from atlas_control import capability


def test_mint_and_redeem_round_trip():
    token = capability.mint("issue_refund", {"claim_number": "CLM-1", "amount_cents": 40000}, "s1")
    cap = capability.redeem(
        token, "issue_refund", {"claim_number": "CLM-1", "amount_cents": 40000}, "s1"
    )
    assert cap.tool == "issue_refund"
    assert cap.session_id == "s1"


def test_redeem_rejects_replay():
    token = capability.mint("search_kb", {"query": "x"}, "s2")
    capability.redeem(token, "search_kb", {"query": "x"}, "s2")
    with pytest.raises(capability.CapabilityError):
        capability.redeem(token, "search_kb", {"query": "x"}, "s2")


def test_redeem_rejects_different_tool():
    token = capability.mint("search_kb", {"query": "x"}, "s3")
    with pytest.raises(capability.CapabilityError):
        capability.redeem(token, "lookup_claim", {"query": "x"}, "s3")


def test_redeem_rejects_different_args():
    token = capability.mint("issue_refund", {"claim_number": "CLM-1", "amount_cents": 40000}, "s4")
    with pytest.raises(capability.CapabilityError):
        capability.redeem(
            token, "issue_refund", {"claim_number": "CLM-1", "amount_cents": 5000000}, "s4"
        )


def test_redeem_rejects_different_session():
    token = capability.mint("search_kb", {"query": "x"}, "s5")
    with pytest.raises(capability.CapabilityError):
        capability.redeem(token, "search_kb", {"query": "x"}, "different-session")


def test_redeem_rejects_garbage_token():
    with pytest.raises(capability.CapabilityError):
        capability.redeem("not-a-real-token", "search_kb", {"query": "x"}, "s6")
