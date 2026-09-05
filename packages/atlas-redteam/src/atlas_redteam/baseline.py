"""Baseline ASR per taxonomy ID, and the regression gate that reads it.

baseline.json maps taxonomy ID -> {asr_ci_low, asr_ci_high} for findings
that have been mitigated by an earlier project (Project 2/3's controls).
Nothing is mitigated by this project alone — the baseline starts empty and
becomes load-bearing once a later project hardens something and reruns this
harness to prove the delta.

A CI gate that only prints a warning is not a gate. `check_regression`
returns a result the CLI turns into a non-zero exit code when a *mitigated*
finding's new ASR lower bound rises above what the baseline says it should
be — that's a real regression, not noise.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from atlas_schema import Finding, FindingStatus

from atlas_redteam.stats import classify


def _primary_taxonomy_id(finding: Finding) -> str:
    return finding.taxonomy[0].id if finding.taxonomy else "untagged"


def load_baseline(path: Path | str) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_baseline(path: Path | str, baseline: dict[str, dict]) -> None:
    Path(path).write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")


def baseline_from_findings(findings: list[Finding]) -> dict[str, dict]:
    """Promote a run's mitigated findings into baseline form."""
    baseline: dict[str, dict] = {}
    for f in findings:
        if f.status != FindingStatus.MITIGATED:
            continue
        baseline[_primary_taxonomy_id(f)] = {
            "asr_ci_low": f.asr_ci_low,
            "asr_ci_high": f.asr_ci_high,
            "finding_id": f.finding_id,
            "run_id": f.run_id,
        }
    return baseline


@dataclass
class RegressionResult:
    regressions: list[Finding] = field(default_factory=list)
    new_findings: list[Finding] = field(default_factory=list)
    flaky: list[Finding] = field(default_factory=list)
    ok: list[Finding] = field(default_factory=list)

    @property
    def has_regression(self) -> bool:
        return len(self.regressions) > 0


def check_regression(findings: list[Finding], baseline: dict[str, dict]) -> RegressionResult:
    result = RegressionResult()
    for f in findings:
        determinism = classify(f.asr, f.asr_ci_low, f.asr_ci_high)
        taxonomy_id = _primary_taxonomy_id(f)
        entry = baseline.get(taxonomy_id)

        if determinism == "flaky":
            result.flaky.append(f)
            continue

        if entry is None:
            result.new_findings.append(f)
            continue

        if f.status == FindingStatus.MITIGATED and f.asr_ci_low > entry["asr_ci_high"]:
            result.regressions.append(f)
        else:
            result.ok.append(f)

    return result
