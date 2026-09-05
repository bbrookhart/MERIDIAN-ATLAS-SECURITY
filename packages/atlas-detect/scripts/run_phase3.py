"""Phase 3 driver: replay the attack corpus, generate benign traffic,
score every detector, build the coverage matrix — against the real
running stack. Writes results to phase3_results.json (repo-root-relative
scratch output, not committed) for the README/dashboard to read.

    uv run --package atlas-detect python packages/atlas-detect/scripts/run_phase3.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import clickhouse_connect
from atlas_detect.clickhouse_schema import ensure_views
from atlas_detect.coverage import build_matrix
from atlas_detect.replay import replay_attack_corpus
from atlas_detect.score import score_all
from atlas_detect.workload_generator import generate_benign_traffic

ATLAS_BASE_URL = "http://127.0.0.1:8000"
OUT_PATH = Path(__file__).resolve().parent / "phase3_results.json"


def main() -> None:
    client = clickhouse_connect.get_client(
        host="127.0.0.1", port=8123, username="default", password="atlas", database="otel"
    )
    ensure_views(client)

    print("Replaying attack corpus...")
    attack_trials = replay_attack_corpus(ATLAS_BASE_URL)
    print(f"  {len(attack_trials)} attack trials replayed")

    print("Generating benign traffic...")
    benign_trials = generate_benign_traffic(ATLAS_BASE_URL, repeats=5)
    print(f"  {len(benign_trials)} benign trials generated")

    print("Scoring detectors...")
    report = score_all(client, ATLAS_BASE_URL, attack_trials, benign_trials)

    print("Building coverage matrix...")
    matrix = build_matrix(report)

    result = {
        "attack_trial_count": len(attack_trials),
        "benign_trial_count": len(benign_trials),
        "scores": [asdict(s) for s in report.scores],
        "unmeasurable": report.unmeasurable,
        "coverage_matrix": matrix,
    }
    OUT_PATH.write_text(json.dumps(result, indent=2, default=str))
    print(f"Wrote {OUT_PATH}")

    for s in report.scores:
        print(
            f"  {s.name}: TP={s.tp} FP={s.fp} FN={s.fn} "
            f"precision={s.precision} recall={s.recall} mttd={s.mttd_seconds}"
        )


if __name__ == "__main__":
    main()
