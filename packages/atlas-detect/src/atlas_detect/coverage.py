"""Detection coverage matrix: OWASP LLM01-10:2026 and ASI01-10 down one
axis, this project's detections across the other, measured recall (from
score.py) in cells where a positive instance exists in the replay corpus
to measure against — and an explicit, one-line reason in every other
cell, per the master prompt's own instruction that an honest matrix with
gaps is more credible than one claiming full coverage.

IDs verified against ai-security-portfolio.md §3 (fetched fresh, not
recalled from training data) rather than a generic web search — three IDs
commonly cited elsewhere have moved in the 2026 revisions.
"""

from __future__ import annotations

from atlas_detect.score import UNMEASURABLE

LLM_IDS = [f"LLM{i:02d}:2026" for i in range(1, 11)]
ASI_IDS = [f"ASI{i:02d}" for i in range(1, 11)]

# detector/rule name -> taxonomy IDs it targets. Sigma rules already
# declare this in their own `tags:` field (see sigma/*.yml) — repeated
# here as plain data because the coverage matrix needs to enumerate
# *every* taxonomy ID including the ones nothing targets, not just walk
# whatever rules happen to exist.
DETECTOR_TAXONOMY: dict[str, list[str]] = {
    "Canary token in any egress path": ["LLM08:2026"],
    "ANSI escape sequence in model output": ["LLM10:2026"],
    "MCP tool description hash drift": ["ASI04"],
    "Tool invocation denied — out-of-scope for role or over policy threshold": [
        "ASI03",
        "LLM03:2026",
    ],
    "plan_deviation": ["ASI01"],
    "tool_sequence_anomaly": ["ASI01"],
    "retrieval_violation": ["LLM02:2026"],
    "memory_poisoning": ["ASI06"],
    "cost_asymmetry": ["LLM06:2026"],
}

# Taxonomy IDs with no detector mapped at all in this project — reasons
# stated per master-prompt instruction, not left blank.
UNCOVERED_TAXONOMY: dict[str, str] = {
    "LLM01:2026": "prompt injection succeeding is a model-behavior question the telemetry layer can observe attempts of (DAN/jailbreak probes) but this project has no detector for it specifically — the structural defenses (Project 2/3) are what actually contain it, not detection",
    "LLM04:2026": "supply-chain risk (dependency/model provenance) isn't observable from request/response telemetry at all",
    "LLM05:2026": "training/fine-tuning-time data poisoning isn't observable from runtime telemetry — Project 2's ingestion-time anomaly detection is the closest control, and it isn't a telemetry-layer detection",
    "LLM07:2026": "misinformation (factual accuracy) isn't a security telemetry signal — no span-level proxy exists for whether a response is *true*",
    "LLM09:2026": "vector/embedding weaknesses (e.g. embedding inversion) require offline analysis of the embedding space itself, not request-level tracing",
    "ASI02": "tool misuse *within* an authorized call (correct tool, correct scope, harmful parameters) isn't distinguishable from legitimate use at the telemetry layer without domain-specific business-logic rules this project doesn't have",
    "ASI05": "unexpected code execution isn't reachable in this deployment at all (Atlas has no code-execution tool, see packages/atlas-control/README.md's gVisor/Firecracker section) — there's nothing to instrument",
    "ASI07": "insecure inter-agent communication doesn't apply — Atlas has no other agents to communicate with",
    "ASI08": "cascading failures across multiple agents isn't reachable for the same reason as ASI07 — single-agent deployment",
    "ASI09": "human-agent trust exploitation is a social-engineering-of-the-human question, not observable in Atlas's own telemetry",
    "ASI10": "rogue agents (an agent acting outside its intended deployment) isn't a scenario this single, centrally-deployed Atlas instance can exhibit",
}


def build_matrix(score_report) -> dict[str, dict]:
    """Returns {taxonomy_id: {"detectors": [...], "recall": {...},
    "uncovered_reason": str | None}}. `score_report` is score.py's
    ScoreReport."""
    recall_by_name = {s.name: s.recall for s in score_report.scores}

    matrix: dict[str, dict] = {}
    for tid in LLM_IDS + ASI_IDS:
        mapped_detectors = [name for name, ids in DETECTOR_TAXONOMY.items() if tid in ids]
        entry = {
            "detectors": mapped_detectors,
            "recall": {name: recall_by_name.get(name) for name in mapped_detectors},
            "uncovered_reason": None,
            "unmeasurable_reason": None,
        }
        if not mapped_detectors:
            entry["uncovered_reason"] = UNCOVERED_TAXONOMY.get(tid, "no detector mapped")
        else:
            unmeasurable_names = [n for n in mapped_detectors if n in UNMEASURABLE]
            if unmeasurable_names:
                entry["unmeasurable_reason"] = "; ".join(
                    f"{n}: {UNMEASURABLE[n]}" for n in unmeasurable_names
                )
        matrix[tid] = entry
    return matrix
