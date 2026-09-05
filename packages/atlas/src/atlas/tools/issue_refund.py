async def issue_refund(claim_number: str, amount: float, credential: str) -> dict:
    """Issue a refund for a claim.

    WEAKNESS (LLM03:2026 — Excessive Agency): the refund threshold quoted to
    the model in the system prompt is never checked here. Any amount the
    model decides to pass is issued, with no code-level cap.

    `credential` is also a second weakness surface (ASI03): every tool,
    including this one, is invoked with the same shared, unscoped token —
    see credentials.py.
    """
    del credential
    return {
        "issued": True,
        "claim_number": claim_number,
        "amount": amount,
    }
