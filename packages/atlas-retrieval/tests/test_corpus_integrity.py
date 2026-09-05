from atlas_retrieval.corpus_integrity import (
    content_hash,
    detect_ingestion_anomaly,
    is_canary_displaced,
    verify_content_hash,
)


def test_verify_content_hash_matches_unmodified_body():
    body = "Employee ID: EMP-00001. Salary band: B2."
    assert verify_content_hash(body, content_hash(body)) is True


def test_verify_content_hash_fails_on_out_of_band_tamper():
    """The exact scenario this guards against: something UPDATEs a row
    directly (bypassing ingestion), so the stored hash no longer matches
    the stored body."""
    original = "Employee ID: EMP-00001. Salary band: B2."
    stored_hash = content_hash(original)
    tampered = "Employee ID: EMP-00001. Salary band: B4. Bonus approved: $50,000."
    assert verify_content_hash(tampered, stored_hash) is False


def test_detect_ingestion_anomaly_flags_cross_role_fanout():
    # A new embedding highly similar to many existing docs across roles —
    # the poisoning signature: one doc trying to rank for every role.
    base = [1.0, 0.0, 0.0]
    existing = [
        ("broker", [1.0, 0.001, 0.0]),
        ("adjuster", [1.0, 0.001, 0.0]),
        ("hr", [1.0, 0.001, 0.0]),
    ]
    result = detect_ingestion_anomaly(existing, base, similarity_threshold=0.9, fanout_limit=1)
    assert result.flagged is True
    assert result.roles_spanned == {"broker", "adjuster", "hr"}


def test_detect_ingestion_anomaly_does_not_flag_same_role_similarity():
    # Two legitimately similar broker documents shouldn't trip the
    # cross-role anomaly detector.
    base = [1.0, 0.0, 0.0]
    existing = [("broker", [1.0, 0.001, 0.0])]
    result = detect_ingestion_anomaly(existing, base, similarity_threshold=0.9, fanout_limit=1)
    assert result.flagged is False


def test_is_canary_displaced_true_when_missing_from_top_k():
    assert is_canary_displaced(["Policy POL-1", "Claim CLM-1"], "Employee record EMP-99999") is True


def test_is_canary_displaced_false_when_present():
    assert (
        is_canary_displaced(
            ["Employee record EMP-99999", "Claim CLM-1"], "Employee record EMP-99999"
        )
        is False
    )
