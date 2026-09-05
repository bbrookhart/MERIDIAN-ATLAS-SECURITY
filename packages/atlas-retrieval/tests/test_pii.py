from atlas_retrieval.pii import redact_pii


def test_redact_pii_strips_ssn():
    text = "Employee SSN: 123-45-6789. Salary band: B2."
    redacted, applied = redact_pii(text)
    assert "123-45-6789" not in redacted
    assert "[REDACTED-SSN]" in redacted
    assert "ssn" in applied


def test_redact_pii_strips_dob():
    text = "DOB: 1990-04-12. Review notes: solid performance."
    redacted, applied = redact_pii(text)
    assert "1990-04-12" not in redacted
    assert "dob" in applied


def test_redact_pii_is_idempotent():
    text = "Employee SSN: 123-45-6789."
    once, _ = redact_pii(text)
    twice, applied_twice = redact_pii(once)
    assert once == twice
    assert applied_twice == []


def test_redact_pii_no_op_on_clean_text():
    text = "Policy number: POL-000123. Coverage type: auto."
    redacted, applied = redact_pii(text)
    assert redacted == text
    assert applied == []
