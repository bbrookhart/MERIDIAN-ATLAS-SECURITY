from atlas_redteam.adapters.garak_adapter import parse_report


def test_parse_report_extracts_trials_from_fixture(fixtures_dir):
    trials = parse_report(fixtures_dir / "garak_report.jsonl")

    # 2 outputs in the first attempt + 1 in the second = 3 trials
    assert len(trials) == 3
    assert sum(1 for t in trials if t.success) == 1  # one detector score >= 0.5

    hit = next(t for t in trials if t.success)
    assert "MERIDIAN-CANARY" in hit.response

    miss = trials[0]
    assert miss.success is False
    assert "Ignore all instructions" in miss.prompt


def test_parse_report_ignores_non_attempt_entries(fixtures_dir):
    trials = parse_report(fixtures_dir / "garak_report.jsonl")
    # the fixture has a start_run and an eval entry that must not become trials
    assert all(t.prompt for t in trials)
