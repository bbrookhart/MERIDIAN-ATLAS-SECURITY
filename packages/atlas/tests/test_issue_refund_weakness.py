from atlas.config import settings
from atlas.credentials import TOOL_CREDENTIAL
from atlas.tools.issue_refund import issue_refund


async def test_issue_refund_has_no_code_level_cap():
    """WEAKNESS (LLM03:2026): the stated refund threshold lives only in the
    system prompt (see prompts.py). issue_refund() must accept any amount.
    """
    amount = settings.refund_threshold_usd * 100
    result = await issue_refund("CLM-00001", amount, TOOL_CREDENTIAL)

    assert result["issued"] is True
    assert result["amount"] == amount
