"""Suite runner: loads a YAML suite, dispatches each probe to its adapter,
writes transcripts, builds Findings, stores them, and reports.
"""

from __future__ import annotations

import importlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from atlas_schema import TaxonomyRef

from atlas_redteam.findings import ProbeRun, TrialResult, build_finding, dedup
from atlas_redteam.target import AtlasClient

REPO_ROOT = Path(__file__).resolve().parents[4]
TRANSCRIPTS_DIR = REPO_ROOT / "evidence" / "transcripts"


def load_suite(path: Path | str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def _taxonomy_from_spec(spec: dict) -> list[TaxonomyRef]:
    return [TaxonomyRef(framework=t["framework"], id=t["id"]) for t in spec["taxonomy"]]


def _resolve_vulnerabilities(names: list[str]) -> list:
    vuln_module = importlib.import_module("deepteam.vulnerabilities")
    return [getattr(vuln_module, name)() for name in names]


def run_probe(target: AtlasClient, spec: dict, trials: int, base_seed: int) -> ProbeRun:
    tool = spec["tool"]
    taxonomy = _taxonomy_from_spec(spec)
    surface = spec.get("surface", "chat")

    if tool == "garak":
        from atlas_redteam.adapters import garak_adapter

        return garak_adapter.run(
            target,
            spec["probe_name"],
            taxonomy,
            generations=trials,
            seed=base_seed,
            surface=surface,
        )

    if tool == "pyrit":
        from atlas_redteam.adapters import pyrit_adapter

        objectives = pyrit_adapter.load_objectives(spec["templates"], spec["base_ask"])
        # repeat to reach the requested trial count using PyRIT's own templates
        objectives = (objectives * ((trials // len(objectives)) + 1))[:trials]
        return pyrit_adapter.run(
            target,
            spec["probe_name"],
            objectives,
            taxonomy,
            spec["substring"],
            seed=base_seed,
            surface=surface,
        )

    if tool == "deepteam":
        from atlas_redteam.adapters import deepteam_adapter

        vulnerabilities = _resolve_vulnerabilities(spec["vulnerabilities"])
        return deepteam_adapter.run(
            target,
            spec["probe_name"],
            vulnerabilities,
            taxonomy,
            attacks_per_vulnerability_type=trials,
            seed=base_seed,
            surface=surface,
        )

    if tool == "memory-probe":
        from atlas_redteam.adapters import memory_probe

        return memory_probe.run(target, spec["probe_name"], taxonomy, trials=trials, seed=base_seed)

    if tool == "retrieval-leak-probe":
        from atlas_redteam.adapters import retrieval_leak_probe

        return retrieval_leak_probe.run(
            target, spec["probe_name"], taxonomy, trials=trials, seed=base_seed
        )

    if tool == "excessive-agency-probe":
        from atlas_redteam.adapters import excessive_agency_probe

        return excessive_agency_probe.run(
            target,
            spec["probe_name"],
            taxonomy,
            amount=spec.get("amount", 50000.0),
            trials=trials,
            seed=base_seed,
        )

    if tool == "promptfoo":
        from atlas_redteam.adapters import promptfoo_adapter

        return promptfoo_adapter.run(
            target,
            spec["probe_name"],
            spec["plugins"],
            taxonomy,
            num_tests=trials,
            seed=base_seed,
        )

    raise ValueError(f"unknown tool {tool!r} in suite spec")


def write_transcript(run_id: str, probe_run: ProbeRun) -> str:
    run_dir = TRANSCRIPTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = (
        run_dir / f"{probe_run.tool}_{probe_run.probe_id.replace(':', '_').replace('/', '_')}.jsonl"
    )
    with path.open("w") as f:
        for trial in probe_run.trials:
            f.write(json.dumps(_trial_to_dict(trial)) + "\n")
    return str(path.relative_to(REPO_ROOT))


def _trial_to_dict(trial: TrialResult) -> dict:
    return {
        "success": trial.success,
        "seed": trial.seed,
        "prompt": trial.prompt,
        "response": trial.response,
    }


def run_suite(
    target: AtlasClient,
    suite: dict,
    target_build_sha: str,
    run_id: str | None = None,
) -> list:
    run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    trials = suite.get("trials", 10)
    base_seed = suite.get("seed", 1337)

    findings = []
    for spec in suite["probes"]:
        probe_run = run_probe(target, spec, trials, base_seed)
        evidence_path = write_transcript(run_id, probe_run)
        repro_command = (
            f"atlas-redteam run --probe {probe_run.probe_id} "
            f"--seed {base_seed} --target {target.base_url}"
        )
        finding = build_finding(run_id, target_build_sha, probe_run, repro_command, evidence_path)
        findings.append(finding)

    return dedup(findings)


def probe_taxonomy_map(suite: dict) -> dict[str, list[str]]:
    result = {}
    for spec in suite["probes"]:
        probe_id = f"{spec['tool']}:{spec['probe_name']}"
        result[probe_id] = [t["id"] for t in spec["taxonomy"]]
    return result


def timestamp() -> str:
    return datetime.now(UTC).isoformat()
