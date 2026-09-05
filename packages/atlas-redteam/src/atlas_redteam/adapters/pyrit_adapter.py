"""PyRIT adapter: wraps Atlas's /chat endpoint as a PyRIT HTTPTarget and
drives it with PyRIT's own PromptSendingAttack + SubStringScorer.

No novel attack techniques are authored: each objective is a neutral,
non-adversarial base question (e.g. "what is your internal reference
token?") wrapped by one of PyRIT's own bundled, published jailbreak
templates (prefix injection, style injection, ...) via
`pyrit.models.SeedPrompt.render_template_value` — the attack technique
itself comes entirely from PyRIT's dataset, not from this code.

HTTPTarget substitutes `{PROMPT}` into a raw HTTP request via plain string
replacement with no JSON escaping, so objectives are escaped the same way
PyRIT's own `JsonStringConverter` does (json.dumps, quotes stripped) before
being sent — this avoids a converter-pipeline dependency while producing an
identical result.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
from pathlib import Path

import pyrit
import pyrit.setup as pyrit_setup
from pyrit.executor.attack import PromptSendingAttack
from pyrit.executor.attack.core.attack_config import AttackScoringConfig
from pyrit.models import SeedPrompt
from pyrit.models.attack_result import AttackOutcome
from pyrit.prompt_target import HTTPTarget, get_http_target_json_response_callback_function
from pyrit.score import SubStringScorer

from atlas_redteam.findings import ProbeRun, TrialResult
from atlas_redteam.target import AtlasClient

PYRIT_DATASETS_DIR = Path(pyrit.__file__).parent / "datasets"
JAILBREAK_TEMPLATES_DIR = PYRIT_DATASETS_DIR / "jailbreak" / "templates"

_initialized = False


async def _ensure_initialized() -> None:
    global _initialized
    if not _initialized:
        await pyrit_setup.initialize_pyrit_async(memory_db_type="InMemory", silent=True)
        _initialized = True


def _escape_for_json(text: str) -> str:
    """Mirrors pyrit.prompt_converter.JsonStringConverter without the pipeline."""
    return json.dumps(text)[1:-1]


def _build_http_request(target: AtlasClient) -> str:
    host = target.base_url.split("://", 1)[1]
    body = json.dumps({"message": "{PROMPT}"})
    return (
        "POST /chat HTTP/1.1\n"
        f"Host: {host}\n"
        "Content-Type: application/json\n"
        f"X-Atlas-Role: {target.role}\n"
        "\n"
        f"{body}"
    )


def load_objectives(template_names: list[str], base_ask: str) -> list[str]:
    objectives = []
    for name in template_names:
        template = SeedPrompt.from_yaml_file(JAILBREAK_TEMPLATES_DIR / f"{name}.yaml")
        objectives.append(template.render_template_value(prompt=base_ask))
    return objectives


async def _run_async(
    target: AtlasClient,
    objectives: list[str],
    taxonomy: list,
    substring: str,
    seed: int,
) -> ProbeRun:
    await _ensure_initialized()

    pyrit_target = HTTPTarget(
        http_request=_build_http_request(target),
        callback_function=get_http_target_json_response_callback_function("reply"),
        use_tls=target.base_url.startswith("https://"),
    )
    scoring_config = AttackScoringConfig(
        objective_scorer=SubStringScorer(substring=substring, categories=["leak"])
    )
    attack = PromptSendingAttack(
        objective_target=pyrit_target, attack_scoring_config=scoring_config
    )

    trials: list[TrialResult] = []
    for i, objective in enumerate(objectives):
        result = await attack.execute_async(objective=_escape_for_json(objective))
        success = result.outcome == AttackOutcome.SUCCESS
        response_text = result.last_response.original_value if result.last_response else ""
        trials.append(
            TrialResult(success=success, seed=seed + i, prompt=objective, response=response_text)
        )

    return ProbeRun(
        tool="pyrit",
        tool_version=importlib.metadata.version("pyrit"),
        probe_id="pyrit:pending",
        taxonomy=taxonomy,
        trials=trials,
    )


def run(
    target: AtlasClient,
    probe_name: str,
    objectives: list[str],
    taxonomy: list,
    substring: str,
    seed: int = 1337,
) -> ProbeRun:
    probe_run = asyncio.run(_run_async(target, objectives, taxonomy, substring, seed))
    probe_run.probe_id = f"pyrit:{probe_name}"
    return probe_run
