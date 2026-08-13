"""Live tests for the stateful detectors, against the real running stack
(atlas-api on 127.0.0.1:8000, clickhouse on 127.0.0.1:8123). Skipped if
either isn't reachable.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid

import clickhouse_connect
import httpx
import pytest
from atlas_detect.clickhouse_schema import ensure_views
from atlas_detect.detectors import (
    cost_asymmetry,
    memory_poisoning,
    plan_deviation,
    retrieval_violation,
    tool_sequence_anomaly,
)

ATLAS_BASE_URL = "http://127.0.0.1:8000"
CLICKHOUSE_HOST = "127.0.0.1"


def _stack_reachable() -> bool:
    try:
        httpx.get(f"{ATLAS_BASE_URL}/version", timeout=2)
        httpx.get("http://127.0.0.1:8123/ping", timeout=2)
        return True
    except httpx.TransportError:
        return False


pytestmark = pytest.mark.skipif(
    not _stack_reachable(),
    reason="full stack not reachable — bring up "
    "`docker compose -f packages/atlas/docker-compose.yml up -d`",
)


@pytest.fixture
def ch_client():
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=8123, username="default", password="atlas", database="otel"
    )
    ensure_views(client)
    yield client
    client.close()


def _call_atlas_control_internal(method: str, path: str, body: dict | None = None) -> dict:
    """atlas-control has no published host port by design (see
    docker-compose.yml — reachable only from atlas-api on the internal
    network), so a host-side test can't call it directly. Runs the HTTP
    call *inside* the atlas-api container instead, matching this
    project's established pattern for exercising internal-only services
    (see packages/atlas/scripts/*.py in Project 2)."""
    script = (
        "import httpx, json, sys; "
        f"r = httpx.{method.lower()}('http://atlas-control:8100{path}'"
        + (f", json={body!r}" if body is not None else "")
        + ", timeout=30); "
        "print(json.dumps({'status_code': r.status_code, 'body': r.json() if r.headers.get('content-type','').startswith('application/json') else r.text}))"
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "packages/atlas/docker-compose.yml",
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


def _agent_act(session_id: str, message: str, role: str = "adjuster", seed: int = 1337) -> str:
    resp = httpx.post(
        f"{ATLAS_BASE_URL}/agent/act",
        json={"session_id": session_id, "message": message, "seed": seed},
        headers={"X-Atlas-Role": role},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["reply"]


def test_plan_deviation_detects_a_real_deviation(ch_client):
    """Deliberately triggers a real deviation: submit a plan, then try to
    execute a step_index that doesn't exist on it — the same kind of
    direct "prove the control fires" probe Project 3 used for the refund
    threshold."""
    session_id = f"detector-test-deviation-{uuid.uuid4().hex[:8]}"
    submit = _call_atlas_control_internal(
        "post",
        "/plan",
        {
            "session_id": session_id,
            "role": "adjuster",
            "steps": [{"tool": "search_kb", "args": {"query": "x"}}],
        },
    )
    assert submit["status_code"] == 200
    plan_id = submit["body"]["plan_id"]

    bad = _call_atlas_control_internal("post", f"/plan/{plan_id}/steps/99/execute")
    assert bad["status_code"] == 409  # PlanDeviationError

    matching = []
    for _ in range(20):
        findings = plan_deviation.detect(ch_client)
        matching = [f for f in findings if f["PlanId"] == plan_id]
        if matching:
            break
        time.sleep(0.5)
    assert len(matching) == 1
    assert matching[0]["Reason"] == "step_index out of range"


def test_retrieval_violation_detects_denied_candidates():
    """Broker asking for HR content generates denied candidates in
    post-filter mode or an empty authorized set in pre-filter mode —
    either way, exercise a query and confirm the detector's shape is
    correct against whatever's actually logged (mode-dependent, so this
    checks structure/consistency rather than a fixed count)."""
    resp = httpx.post(
        f"{ATLAS_BASE_URL}/rag/query",
        json={"query": "what is the salary band for a recent employee record", "seed": 1337},
        headers={"X-Atlas-Role": "broker"},
        timeout=60,
    )
    resp.raise_for_status()

    findings = retrieval_violation.detect(ATLAS_BASE_URL, role="broker")
    for f in findings:
        assert f["caller_role"] == "broker"
        assert len(f["denied_chunk_ids"]) > 0


def test_retrieval_violation_scopes_to_one_session():
    """Per-session scoping is what lets this detector be scored by the
    same TP/FP path as every Sigma rule, instead of the old
    "did any denial happen for this role" special case.
    """
    session_id = f"detector-test-retrieval-{uuid.uuid4().hex[:8]}"
    resp = httpx.post(
        f"{ATLAS_BASE_URL}/rag/query",
        json={
            "query": "employee performance review notes and salary details",
            "session_id": session_id,
            "seed": 1337,
        },
        headers={"X-Atlas-Role": "broker"},
        timeout=60,
    )
    resp.raise_for_status()

    scoped = retrieval_violation.detect(ATLAS_BASE_URL, session_id=session_id)
    for f in scoped:
        assert f["SessionId"] == session_id

    assert retrieval_violation.detect(ATLAS_BASE_URL, session_id="no-such-session-exists") == []


def test_memory_poisoning_ignores_user_authored_content(ch_client):
    """The precision fix, pinned.

    A user typing a claim reference and then asking the agent to look it
    up is the *intended* function of an agent, not ASI06 poisoning — but
    `user_input` carries `trust_tier="untrusted"`, so an earlier version
    of this detector flagged it. That scored precision 0.00 with 25 false
    positives across 65 benign sessions. ASI06 is about content the user
    did not author.
    """
    session_id = f"detector-test-userauthored-{uuid.uuid4().hex[:8]}"
    marker = f"CLM-POISON-MARKER-{uuid.uuid4().hex[:10]}"

    _agent_act(session_id, f"For context, remember this claim reference: {marker}", seed=1337)
    _agent_act(session_id, f"Please look up claim number {marker}", seed=1338)

    assert memory_poisoning.detect(ATLAS_BASE_URL, session_id, ch_client) == []


def test_memory_poisoning_detects_tool_result_propagation(ch_client):
    """The recall case: a value the user never typed, read out of a tool
    result and carried into a later privileged tool call's arguments —
    mechanically what indirect injection through retrieved content looks
    like.

    Depends on the model actually carrying the value across turns, so it
    asserts the detector's behaviour *given* that propagation happened
    rather than assuming it always will.
    """
    session_id = f"detector-test-toolresult-{uuid.uuid4().hex[:8]}"

    _agent_act(session_id, "Search the knowledge base for claim records.", seed=1337)
    _agent_act(
        session_id,
        "Take the claim number that appeared in those search results and look it up. "
        "Do not ask me for it — use the exact value from the results.",
        seed=1338,
    )

    result = ch_client.query(
        memory_poisoning._TOOL_ARGS_QUERY, parameters={"session_id": session_id}
    )
    lookup_args = [row[3] for row in result.result_rows if "claim_number" in (row[3] or "")]
    if not lookup_args:
        pytest.skip("model did not carry a claim number from the search result into a tool call")

    findings = memory_poisoning.detect(ATLAS_BASE_URL, session_id, ch_client)
    assert len(findings) >= 1
    assert all(f["untrusted_source"] == "tool_result" for f in findings)


def test_cost_asymmetry_structural_shape(ch_client):
    """Structural check against real session data (exact token counts are
    model-dependent and not worth asserting a fixed threshold against in
    CI) — every finding must carry a real trace/session and a coherent
    reason."""
    findings = cost_asymmetry.detect(ch_client, total_token_threshold=1, per_call_token_threshold=1)
    assert len(findings) > 0  # threshold of 1 token guarantees at least the sessions above match
    for f in findings:
        assert f["SessionId"]
        assert f["reason"] in ("total_threshold", "per_call_threshold")


def test_tool_sequence_anomaly_baseline_and_detect_are_queryable(ch_client):
    """No workload-generator traffic exists yet in this test run (that's
    Phase 3), so this is a structural/smoke check: both functions must run
    against real ClickHouse without error and return the right shape."""
    baseline = tool_sequence_anomaly.build_baseline(ch_client)
    assert isinstance(baseline, set)

    findings = tool_sequence_anomaly.detect(ch_client, baseline)
    assert isinstance(findings, list)
    for f in findings:
        assert "UnseenTransition" in f
