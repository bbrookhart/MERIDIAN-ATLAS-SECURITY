from atlas_assurance.ingest.findings import load_findings
from atlas_assurance.registry import CONTROLS


def test_control_ids_are_unique() -> None:
    ids = [c.control_id for c in CONTROLS]
    assert len(ids) == len(set(ids))


def test_every_control_has_a_well_formed_test_ref() -> None:
    for c in CONTROLS:
        assert "::" in c.test_ref, c.control_id


def test_control_refs_sourced_from_real_findings_actually_match_a_real_finding() -> None:
    """The three controls whose control_ref was copied from a real
    mitigated Finding must still match at least one real finding in the
    committed DB — this is the traceability the registry's own docstring
    claims, checked live rather than assumed.
    """
    findings = load_findings()
    real_control_refs = {f.control_ref for f in findings if f.control_ref}

    sourced_from_findings = {
        "tool-authorization-refund-threshold",
        "session-scoped-memory",
        "retrieval-authorization",
    }
    for control in CONTROLS:
        if control.control_id in sourced_from_findings:
            assert control.control_ref in real_control_refs, control.control_id
