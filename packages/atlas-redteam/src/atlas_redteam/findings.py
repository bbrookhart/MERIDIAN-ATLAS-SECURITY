"""Builds atlas_schema.Finding objects from raw trial results, and dedups
across tools.

Deduplication heuristic (documented plainly, per the spec, including its
failure mode): findings are grouped by (target_build_sha, primary taxonomy
ID). When two different tools land a finding on the same primary taxonomy
ID against the same build, they're collapsed into one Finding with both
probe_ids retained and counts pooled. This assumes "same taxonomy ID" means
"same underlying weakness" — that's often true (e.g. two different prompt-
injection probes both landing on LLM01:2026 via the same unguarded RAG
concatenation) but not always: two tools can both trip LLM01:2026 through
genuinely different code paths, and this heuristic will merge them anyway.
Treat a merged finding's combined ASR as a ceiling on how many *distinct*
root causes it represents, not a guarantee there's exactly one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from atlas_schema import Finding, FindingStatus, TaxonomyRef

from atlas_redteam.stats import wilson_interval


@dataclass
class TrialResult:
    """One trial: one probe sent to Atlas, one judgment of success/failure."""

    success: bool
    seed: int
    prompt: str
    response: str


@dataclass
class ProbeRun:
    """Everything needed to turn a completed probe's trials into a Finding."""

    tool: str
    tool_version: str
    probe_id: str
    taxonomy: list[TaxonomyRef]
    trials: list[TrialResult] = field(default_factory=list)


def build_finding(
    run_id: str,
    target_build_sha: str,
    probe_run: ProbeRun,
    repro_command: str,
    evidence_path: str | None = None,
) -> Finding:
    if not probe_run.trials:
        raise ValueError(f"probe {probe_run.probe_id} has zero trials — nothing to report")

    attempts = len(probe_run.trials)
    successes = sum(1 for t in probe_run.trials if t.success)
    interval = wilson_interval(successes, attempts)
    base_seed = probe_run.trials[0].seed

    return Finding(
        finding_id=f"F-{uuid.uuid4()}",
        run_id=run_id,
        timestamp=datetime.now(UTC),
        target_build_sha=target_build_sha,
        tool=probe_run.tool,
        tool_version=probe_run.tool_version,
        probe_id=probe_run.probe_id,
        taxonomy=probe_run.taxonomy,
        attempts=attempts,
        successes=successes,
        asr=interval.asr,
        asr_ci_low=interval.ci_low,
        asr_ci_high=interval.ci_high,
        ci_method="wilson",
        seed=base_seed,
        evidence_path=evidence_path,
        repro_command=repro_command,
        status=FindingStatus.OPEN,
        control_ref=None,
        retest_run_id=None,
    )


def _primary_taxonomy_id(finding: Finding) -> str:
    return finding.taxonomy[0].id if finding.taxonomy else "untagged"


def dedup(findings: list[Finding]) -> list[Finding]:
    groups: dict[tuple[str, str], list[Finding]] = {}
    for f in findings:
        key = (f.target_build_sha, _primary_taxonomy_id(f))
        groups.setdefault(key, []).append(f)

    merged: list[Finding] = []
    for group in groups.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        merged.append(_merge(group))
    return merged


def _merge(group: list[Finding]) -> Finding:
    attempts = sum(f.attempts for f in group)
    successes = sum(f.successes for f in group)
    interval = wilson_interval(successes, attempts)

    seen_taxonomy: dict[tuple[str, str], TaxonomyRef] = {}
    for f in group:
        for ref in f.taxonomy:
            seen_taxonomy[(ref.framework, ref.id)] = ref

    tools = "+".join(sorted({f.tool for f in group}))
    probe_ids = "+".join(sorted({f"{f.tool}:{f.probe_id}" for f in group}))
    latest = max(group, key=lambda f: f.timestamp)

    return Finding(
        finding_id=f"F-{uuid.uuid4()}",
        run_id=latest.run_id,
        timestamp=latest.timestamp,
        target_build_sha=latest.target_build_sha,
        tool=tools,
        tool_version="merged",
        probe_id=probe_ids,
        taxonomy=list(seen_taxonomy.values()),
        attempts=attempts,
        successes=successes,
        asr=interval.asr,
        asr_ci_low=interval.ci_low,
        asr_ci_high=interval.ci_high,
        ci_method="wilson",
        seed=latest.seed,
        evidence_path=latest.evidence_path,
        repro_command=latest.repro_command,
        status=FindingStatus.OPEN,
        control_ref=None,
        retest_run_id=None,
    )
