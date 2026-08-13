"""Phase 3 driver: replay the attack corpus, generate benign traffic,
score every detector, build the coverage matrix — against the real
running stack.

`--mode` records which ATLAS_RETRIEVAL_MODE the stack is running in and
picks the output filename accordingly, so the pre- and post-filter runs
don't overwrite each other. It does *not* set the mode — bring the stack
up with `ATLAS_RETRIEVAL_MODE=post docker compose ... up -d` first. The
mode matters because retrieval_violation reads a denial log that only has
entries in post-filter mode.

    uv run --package atlas-detect python packages/atlas-detect/scripts/run_phase3.py
    uv run --package atlas-detect python packages/atlas-detect/scripts/run_phase3.py --mode post
"""

from __future__ import annotations

import argparse
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
SCRIPTS_DIR = Path(__file__).resolve().parent


def _out_path(mode: str) -> Path:
    return SCRIPTS_DIR / ("phase3_results.json" if mode == "pre" else f"phase3_results_{mode}.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["pre", "post"],
        default="pre",
        help="which ATLAS_RETRIEVAL_MODE the running stack is configured with",
    )
    args = parser.parse_args()
    out_path = _out_path(args.mode)
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
        "retrieval_mode": args.mode,
        "attack_trial_count": len(attack_trials),
        "benign_trial_count": len(benign_trials),
        "scores": [asdict(s) for s in report.scores],
        "unmeasurable": report.unmeasurable,
        "coverage_matrix": matrix,
    }
    out_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"Wrote {out_path}")

    for s in report.scores:
        print(
            f"  {s.name}: TP={s.tp} FP={s.fp} FN={s.fn} "
            f"precision={s.precision} recall={s.recall} mttd={s.mttd_seconds}"
        )


if __name__ == "__main__":
    main()
