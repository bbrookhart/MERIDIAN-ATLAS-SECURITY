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

Same seed limitation as garak_adapter: the raw HTTP request template has no
slot for Atlas's `seed` field, so trial-to-trial and *run-to-run* variation
here comes from Atlas's own unseeded sampling. Recorded `Finding.seed`
values are bookkeeping only. This was confirmed materially in Project 3's
Phase A/C comparison: the PyRIT- and garak-sourced findings moved between
runs with no code-level change able to explain the difference (Atlas's
`/agent/act` prompt-completion path is untouched by the control-plane
rewrite), while the two custom probes in `memory_probe.py` and
`excessive_agency_probe.py` — which *do* forward a real seed via
`AtlasClient.agent_act(..., seed=...)` — moved in a way directly
attributable to the code change. Don't treat a PyRIT/garak ASR delta
between two runs as evidence of anything without a seeded, apples-to-apples
adapter to corroborate it.
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


def _build_http_request(
    target: AtlasClient, surface: str = "chat", session_id: str | None = None
) -> str:
    """surface: "chat" (POST /chat), "agent" (POST /agent/act), or "rag"
    (POST /rag/query).

    For "agent", session_id is a single fixed value for the whole probe run —
    PyRIT's HTTPTarget only exposes one {PROMPT} substitution point, so a
    per-request session id isn't achievable through it either (same
    limitation as garak_adapter's build_generator_config).
    """
    host = target.base_url.split("://", 1)[1]
    if surface == "agent":
        path = "/agent/act"
        body = json.dumps({"session_id": session_id or "pyrit-agent-probe", "message": "{PROMPT}"})
    elif surface == "rag":
        path = "/rag/query"
        body = json.dumps({"query": "{PROMPT}"})
    else:
        path = "/chat"
        body = json.dumps({"message": "{PROMPT}"})
    return (
        f"POST {path} HTTP/1.1\n"
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
    surface: str,
    session_id: str | None,
) -> ProbeRun:
    await _ensure_initialized()

    pyrit_target = HTTPTarget(
        http_request=_build_http_request(target, surface=surface, session_id=session_id),
        callback_function=get_http_target_json_response_callback_function("reply"),
        use_tls=target.base_url.startswith("https://"),
        # /agent/act runs a multi-step tool-calling loop (LLM + MCP round
        # trips) and can take much longer than /chat's single call; httpx's
        # default timeout is far too short for it.
        timeout=120,
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
    surface: str = "chat",
) -> ProbeRun:
    session_id = f"pyrit-{probe_name}-{seed}"
    probe_run = asyncio.run(
        _run_async(target, objectives, taxonomy, substring, seed, surface, session_id)
    )
    probe_run.probe_id = f"pyrit:{probe_name}"
    return probe_run
