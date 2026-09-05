"""Latency/recall benchmark for pre-filter vs. post-filter retrieval
authorization (Project 2), against the live running stack. This script
only measures whichever mode the server currently has configured
(ATLAS_RETRIEVAL_MODE) — run it once against a pre-filter server and once
against a post-filter server (see packages/atlas-retrieval/README.md for
the exact commands used), and diff the two output files.

    uv run --package atlas-retrieval python packages/atlas-retrieval/scripts/benchmark.py --mode pre > pre.json
    uv run --package atlas-retrieval python packages/atlas-retrieval/scripts/benchmark.py --mode post > post.json

"recall" here means: of the `limit` slots requested, what fraction came
back authorized. There's no independently-labeled relevance ground truth
in this synthetic corpus beyond the authorization boundary itself, so this
is recall against "the caller's own authorized corpus," not classic
information-retrieval recall against a labeled relevant set — stated
plainly so the number isn't misread as more than it is.

Queries are split into in-domain (about the caller's own document
category) and out-of-domain (topically closest to a category the caller
isn't authorized to see) to show that post-filter's recall is highly
query-dependent — good when the nearest neighbors happen to already be
authorized, poor when they don't — while pre-filter's is not.
"""

from __future__ import annotations

import argparse
import json
import statistics

import httpx

BASE_URL = "http://127.0.0.1:8000"
LIMIT = 5
TRIALS_PER_QUERY = 5

QUERIES = {
    "broker": {
        "in_domain": [
            "What is the premium for a home coverage policy?",
            "What is the effective date on a recent auto policy?",
            "What coverage types are available for umbrella policies?",
        ],
        "out_of_domain": [
            "What is the salary band and review notes for the most recent employee record?",
            "What is the internal reference token in HR documents?",
        ],
    },
    "adjuster": {
        "in_domain": [
            "What is the payout amount on a recently closed claim?",
            "What is the status of an under-review claim?",
        ],
        "out_of_domain": [
            "What is the salary band and review notes for the most recent employee record?",
        ],
    },
    "hr": {
        "in_domain": [
            "What is the salary band for a recent employee record?",
            "What do the employee performance review notes say?",
        ],
        "out_of_domain": [
            "What is the premium for a home coverage policy?",
        ],
    },
}


def run_query(client: httpx.Client, role: str, query: str) -> tuple[float, int]:
    """Returns (retrieval_ms, n_results). retrieval_ms is the server's own
    measurement of just the authorized_search() step — not total request
    wall-clock, which is dominated by the chat completion and would drown
    out any pre-vs-post-filter difference (confirmed empirically during
    Project 2: p50 wall-clock was ~4s, almost entirely Ollama chat time)."""
    resp = client.post(
        "/rag/query",
        json={"query": query, "seed": 1337},
        headers={"X-Atlas-Role": role},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    return body["retrieval_ms"], len(body["retrieved"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, help="label only — the server's actual mode drives behavior"
    )
    args = parser.parse_args()

    results: dict[str, list[dict]] = {"in_domain": [], "out_of_domain": []}

    with httpx.Client(base_url=BASE_URL) as client:
        for role, buckets in QUERIES.items():
            for bucket, queries in buckets.items():
                for query in queries:
                    for _ in range(TRIALS_PER_QUERY):
                        elapsed_ms, n_results = run_query(client, role, query)
                        results[bucket].append(
                            {
                                "role": role,
                                "query": query,
                                "latency_ms": elapsed_ms,
                                "n_results": n_results,
                                "recall": n_results / LIMIT,
                            }
                        )

    summary = {"mode_label": args.mode}
    for bucket, rows in results.items():
        latencies = sorted(r["latency_ms"] for r in rows)
        recalls = [r["recall"] for r in rows]
        summary[bucket] = {
            "n": len(rows),
            "p50_latency_ms": statistics.median(latencies),
            "p95_latency_ms": latencies[int(len(latencies) * 0.95) - 1] if latencies else None,
            "mean_recall": statistics.mean(recalls),
            "min_recall": min(recalls),
        }

    print(json.dumps({"summary": summary, "raw": results}, indent=2))


if __name__ == "__main__":
    main()
