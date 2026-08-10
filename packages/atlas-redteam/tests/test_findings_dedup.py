from datetime import UTC, datetime

from atlas_redteam.findings import ProbeRun, TrialResult, build_finding, dedup
from atlas_schema import Finding, FindingStatus, TaxonomyFramework, TaxonomyRef


def make_finding(tool: str, probe_id: str, taxonomy_id: str, attempts=10, successes=5) -> Finding:
    return Finding(
        finding_id=f"F-{tool}-{probe_id}",
        run_id="run-1",
        timestamp=datetime(2026, 8, 9, tzinfo=UTC),
        target_build_sha="a" * 40,
        tool=tool,
        tool_version="0.1.0",
        probe_id=probe_id,
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id=taxonomy_id)],
        attempts=attempts,
        successes=successes,
        asr=successes / attempts,
        asr_ci_low=max(0.0, successes / attempts - 0.2),
        asr_ci_high=min(1.0, successes / attempts + 0.2),
        seed=1337,
        evidence_path=None,
        repro_command=f"atlas-redteam run --probe {probe_id}",
        status=FindingStatus.OPEN,
        control_ref=None,
        retest_run_id=None,
    )


def test_dedup_merges_same_taxonomy_across_tools():
    f1 = make_finding("garak", "probe-a", "LLM01:2026", attempts=10, successes=5)
    f2 = make_finding("pyrit", "probe-b", "LLM01:2026", attempts=10, successes=3)

    merged = dedup([f1, f2])

    assert len(merged) == 1
    result = merged[0]
    assert result.attempts == 20
    assert result.successes == 8
    assert "garak" in result.tool and "pyrit" in result.tool
    assert "garak:probe-a" in result.probe_id and "pyrit:probe-b" in result.probe_id


def test_dedup_leaves_distinct_taxonomy_ids_separate():
    f1 = make_finding("garak", "probe-a", "LLM01:2026")
    f2 = make_finding("pyrit", "probe-b", "LLM03:2026")

    merged = dedup([f1, f2])

    assert len(merged) == 2


def test_build_finding_computes_wilson_ci_from_trials():
    probe_run = ProbeRun(
        tool="garak",
        tool_version="0.16.0",
        probe_id="latentinjection.LatentInjectionFactSnippetEiffel",
        taxonomy=[TaxonomyRef(framework=TaxonomyFramework.OWASP_LLM_2026, id="LLM01:2026")],
        trials=[
            TrialResult(success=True, seed=1337, prompt="p1", response="r1"),
            TrialResult(success=False, seed=1338, prompt="p2", response="r2"),
            TrialResult(success=True, seed=1339, prompt="p3", response="r3"),
        ],
    )

    finding = build_finding("run-1", "a" * 40, probe_run, "atlas-redteam run --probe x --seed 1337")

    assert finding.attempts == 3
    assert finding.successes == 2
    assert finding.seed == 1337
    assert finding.asr_ci_low <= finding.asr <= finding.asr_ci_high
