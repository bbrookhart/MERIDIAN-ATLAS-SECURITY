from atlas_redteam.adapters.promptfoo_adapter import parse_results


def test_parse_results_extracts_trials_from_fixture(fixtures_dir):
    trials = parse_results(fixtures_dir / "promptfoo_results.json")

    assert len(trials) == 2
    # promptfoo success=True means the assertion passed (target stayed safe);
    # success=False means the attack got through.
    safe, vulnerable = trials
    assert safe.success is False
    assert vulnerable.success is True
    assert "MERIDIAN-CANARY" in vulnerable.response
