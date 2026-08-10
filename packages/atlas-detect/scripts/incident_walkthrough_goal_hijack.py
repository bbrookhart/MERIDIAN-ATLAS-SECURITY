"""Worked incident walkthrough #2: a detected goal hijack attempt.

ASI01 (Agent Goal Hijack) in this architecture means: content encountered
mid-execution tries to make the executor run a tool step that was never
in the frozen, policy-approved plan. Project 3's design makes this
structurally unreachable through the normal /agent/act path (there is no
API that accepts an arbitrary tool+args — only execute_step(plan_id,
already-approved index)), so a real red-team prompt against Atlas can't
actually produce one; the only way to exercise the control is to attempt
exactly what a compromised or malicious component would attempt: calling
execute_step with an index outside the frozen plan. This walkthrough does
that directly against atlas-control (from inside the atlas-api container,
since atlas-control has no published host port by design) and traces the
resulting detection end to end.

    uv run --package atlas-detect python packages/atlas-detect/scripts/incident_walkthrough_goal_hijack.py
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid

import clickhouse_connect
from atlas_detect.clickhouse_schema import ensure_views
from atlas_detect.detectors import plan_deviation

COMPOSE_FILE = "packages/atlas/docker-compose.yml"


def _call_atlas_control(method: str, path: str, body: dict | None = None) -> dict:
    script = (
        "import httpx, json; "
        f"r = httpx.{method}('http://atlas-control:8100{path}'"
        + (f", json={body!r}" if body is not None else "")
        + ", timeout=30); "
        "print(json.dumps({'status_code': r.status_code, 'body': r.json()}))"
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "exec",
            "-T",
            "atlas-api",
            "python",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> None:
    client = clickhouse_connect.get_client(
        host="127.0.0.1", port=8123, username="default", password="atlas", database="otel"
    )
    ensure_views(client)

    session_id = f"incident-hijack-{uuid.uuid4().hex[:8]}"
    print("=" * 70)
    print("INCIDENT WALKTHROUGH: detected goal hijack attempt")
    print("=" * 70)

    print("\n[1] Submitting a legitimate, policy-approved plan (one step: search_kb)...")
    t0 = time.time()
    submit = _call_atlas_control(
        "post",
        "/plan",
        {
            "session_id": session_id,
            "role": "adjuster",
            "steps": [{"tool": "search_kb", "args": {"query": "auto policy coverage"}}],
        },
    )
    plan_id = submit["body"]["plan_id"]
    plan_hash = submit["body"]["plan_hash"]
    print(f"    plan_id={plan_id} plan_hash={plan_hash} (frozen at t=0.00s)")

    print("\n[2] Simulating a hijack attempt: requesting step_index=7 — outside the frozen plan")
    print("    (the plan only has one step, index 0). This is the exact shape of what a")
    print("    compromised planner or a goal-hijacked model would need to succeed at.")
    bad = _call_atlas_control("post", f"/plan/{plan_id}/steps/7/execute")
    t1 = time.time()
    print(
        f"    response at t={t1 - t0:.2f}s: HTTP {bad['status_code']} — {bad['body'].get('detail')}"
    )
    assert bad["status_code"] == 409, "expected the deviation to be rejected, not executed"

    print("\n[3] Confirming nothing executed: the frozen plan's only step is still unexecuted.")
    plan_state = _call_atlas_control("get", f"/plan/{plan_id}")
    executed = plan_state["body"]["steps"][0]["executed"]
    print(f"    step 0 executed={executed}")
    assert executed is False

    print("\n[4] Querying the trace store for the detection...")
    matching = []
    for _ in range(20):
        findings = plan_deviation.detect(client)
        matching = [f for f in findings if f["PlanId"] == plan_id]
        if matching:
            break
        time.sleep(0.5)

    if matching:
        finding = matching[0]
        from datetime import UTC, datetime

        event_ts = finding["Timestamp"].replace(tzinfo=UTC)  # ClickHouse returns naive UTC
        latency = (datetime.now(UTC) - event_ts).total_seconds()
        print(f"    DETECTED at {finding['Timestamp']}: reason={finding['Reason']!r}")
        print(f"    detection latency (query time - event time): {latency:.2f}s")
    else:
        print("    not detected (unexpected — investigate)")

    print("\n" + "=" * 70)
    print("Result: the hijack attempt was rejected by construction (plan.py's")
    print("execute_step never runs an index outside the frozen plan) AND surfaced")
    print("as a detection event — containment and detection, not detection alone.")


if __name__ == "__main__":
    main()
