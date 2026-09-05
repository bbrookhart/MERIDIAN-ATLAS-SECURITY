"""promptfoo adapter: subprocess npx invocation against a declarative YAML
config — no novel attack payloads, promptfoo's own redteam plugins (e.g.
its OWASP Agentic preset) generate and grade the test cases.

promptfoo requires Node >= 22; this machine's default `npx` (via nvm) may
resolve to an older version, so a suitable node/npx pair is located
explicitly rather than assumed to be on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from atlas_redteam.findings import ProbeRun, TrialResult
from atlas_redteam.target import AtlasClient

MIN_NODE_MAJOR = 22
PROMPTFOO_VERSION = "promptfoo@latest"


def _node_major_version(node_path: Path) -> int | None:
    try:
        result = subprocess.run(
            [str(node_path), "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    version = result.stdout.strip().lstrip("v")
    try:
        return int(version.split(".")[0])
    except (ValueError, IndexError):
        return None


def find_npx() -> str:
    """Locate an npx backed by Node >= 22, checking PATH then nvm installs."""
    default_npx = shutil.which("npx")
    if default_npx:
        node_path = Path(default_npx).parent / "node"
        major = _node_major_version(node_path)
        if major is not None and major >= MIN_NODE_MAJOR:
            return default_npx

    nvm_node_dir = Path.home() / ".nvm" / "versions" / "node"
    if nvm_node_dir.is_dir():
        for candidate in sorted(nvm_node_dir.iterdir(), reverse=True):
            candidate_node = candidate / "bin" / "node"
            candidate_npx = candidate / "bin" / "npx"
            major = _node_major_version(candidate_node)
            if candidate_npx.exists() and major is not None and major >= MIN_NODE_MAJOR:
                return str(candidate_npx)

    raise RuntimeError(
        f"promptfoo requires Node >= {MIN_NODE_MAJOR}; no suitable npx found on PATH "
        "or under ~/.nvm/versions/node. Install a newer Node (e.g. `nvm install 22`)."
    )


def build_config(target: AtlasClient) -> dict:
    return {
        "targets": [
            {
                "id": "http",
                "config": {
                    "url": f"{target.base_url}/chat",
                    "method": "POST",
                    "headers": {
                        "X-Atlas-Role": target.role,
                        "Content-Type": "application/json",
                    },
                    "body": {"message": "{{prompt}}"},
                    "transformResponse": "json.reply",
                },
            }
        ],
    }


def run_promptfoo(
    npx: str, config_path: Path, plugins: list[str], num_tests: int, workdir: Path
) -> Path:
    tests_path = workdir / "redteam.yaml"
    results_path = workdir / "results.json"

    subprocess.run(
        [
            npx,
            "--yes",
            PROMPTFOO_VERSION,
            "redteam",
            "generate",
            "-c",
            str(config_path),
            "-o",
            str(tests_path),
            "--plugins",
            ",".join(plugins),
            "-n",
            str(num_tests),
            "--no-cache",
            "--no-progress-bar",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=workdir,
    )
    subprocess.run(
        [npx, "--yes", PROMPTFOO_VERSION, "eval", "-c", str(tests_path), "-o", str(results_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=workdir,
    )
    return results_path


def parse_results(results_path: Path) -> list[TrialResult]:
    """Pure function — independently testable against a recorded fixture."""
    data = json.loads(results_path.read_text())
    rows = data.get("results", {}).get("results", [])

    trials: list[TrialResult] = []
    for row in rows:
        prompt = _extract_prompt(row)
        response = _extract_response(row)
        success = row.get("success") is False  # promptfoo "success" = assertion passed = safe
        trials.append(TrialResult(success=success, seed=0, prompt=prompt, response=response))
    return trials


def _extract_prompt(row: dict) -> str:
    vars_ = row.get("vars", {})
    if isinstance(vars_, dict) and "prompt" in vars_:
        return str(vars_["prompt"])
    return str(row.get("prompt", {}).get("raw", "")) if isinstance(row.get("prompt"), dict) else ""


def _extract_response(row: dict) -> str:
    response = row.get("response", {})
    if isinstance(response, dict):
        return str(response.get("output", ""))
    return str(response) if response else ""


def run(
    target: AtlasClient,
    probe_name: str,
    plugins: list[str],
    taxonomy: list,
    num_tests: int = 5,
    seed: int = 1337,
    workdir: Path | None = None,
) -> ProbeRun:
    npx = find_npx()
    config = build_config(target)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(workdir) if workdir else Path(tmp)
        base.mkdir(parents=True, exist_ok=True)
        config_path = base / "promptfooconfig.yaml"
        config_path.write_text(yaml.safe_dump(config))

        results_path = run_promptfoo(npx, config_path, plugins, num_tests, base)
        trials = parse_results(results_path)

    for i, trial in enumerate(trials):
        trial.seed = seed + i

    return ProbeRun(
        tool="promptfoo",
        tool_version="latest",
        probe_id=f"promptfoo:{probe_name}",
        taxonomy=taxonomy,
        trials=trials,
    )
