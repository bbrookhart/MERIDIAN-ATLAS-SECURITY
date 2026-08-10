"""Replay harness — the master prompt's stated core contribution: take
Project 1's already-labelled attack corpus (real transcripts from real
red-team runs against the real stack, not synthesized) and replay each
prompt against the *now-instrumented* Atlas, producing fresh traces this
project's detectors can actually be measured against.

The old transcripts predate telemetry entirely (Projects 1-3 ran before
Project 4 existed), so a trace has to be regenerated — this replays the
same prompt text, not the same trace. Every replayed session gets a
`replay-attack-` session_id prefix (agent surface) so
tool_sequence_anomaly's baseline/eval split can tell it apart from
workload_generator.py's `workload-benign-` traffic without a separate
labeling side-channel.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from atlas_detect._retry import with_retry

REPO_ROOT = Path(__file__).resolve().parents[4]
TRANSCRIPTS_DIR = REPO_ROOT / "evidence" / "transcripts"

# (transcript dir name, surface, role) — the surface/role a probe targeted
# isn't recorded in the transcript itself (only prompt/seed/success/
# response are), so this is where that mapping is declared explicitly.
ATTACK_CORPUS = [
    ("phase_c_agent_baseline", "agent", "adjuster"),
    ("phase_c_rag_authorization", "rag", "broker"),
]


@dataclass(frozen=True)
class ReplayedTrial:
    probe_file: str
    prompt: str
    original_success: bool
    surface: str
    role: str
    session_id: str | None
    request_id: str
    reply: str
    canary_leaked: bool


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _replay_one(
    client: httpx.Client, surface: str, role: str, prompt: str, session_id: str | None
) -> str:
    headers = {"X-Atlas-Role": role}

    def _send() -> httpx.Response:
        if surface == "agent":
            resp = client.post(
                "/agent/act",
                json={"session_id": session_id, "message": prompt, "seed": 1337},
                headers=headers,
                timeout=90,
            )
        elif surface == "rag":
            resp = client.post(
                "/rag/query",
                json={"query": prompt, "session_id": session_id, "seed": 1337},
                headers=headers,
                timeout=90,
            )
        else:
            resp = client.post(
                "/chat", json={"message": prompt, "seed": 1337}, headers=headers, timeout=90
            )
        resp.raise_for_status()
        return resp

    return with_retry(_send).json().get("reply", "")


def replay_attack_corpus(
    atlas_base_url: str,
    corpus: list[tuple[str, str, str]] | None = None,
    transcripts_dir: Path | None = None,
    delay_seconds: float = 0.0,
) -> list[ReplayedTrial]:
    corpus = corpus or ATTACK_CORPUS
    transcripts_dir = transcripts_dir or TRANSCRIPTS_DIR

    replayed: list[ReplayedTrial] = []
    with httpx.Client(base_url=atlas_base_url) as client:
        for dir_name, surface, role in corpus:
            probe_dir = transcripts_dir / dir_name
            if not probe_dir.exists():
                continue
            for probe_file in sorted(probe_dir.glob("*.jsonl")):
                trials = _load_jsonl(probe_file)
                for i, trial in enumerate(trials):
                    session_id = (
                        f"replay-attack-{probe_file.stem}-{i}-{uuid.uuid4().hex[:6]}"
                        if surface in ("agent", "rag")
                        else None
                    )
                    request_id = str(uuid.uuid4())
                    reply = _replay_one(client, surface, role, trial["prompt"], session_id)
                    replayed.append(
                        ReplayedTrial(
                            probe_file=probe_file.stem,
                            prompt=trial["prompt"],
                            original_success=trial["success"],
                            surface=surface,
                            role=role,
                            session_id=session_id,
                            request_id=request_id,
                            reply=reply,
                            # Ground truth for *this* live replay, not the
                            # old transcript's (possibly different, since
                            # sampling isn't guaranteed identical across
                            # runs — see pyrit_adapter.py's documented
                            # unseeded-sampling limitation) recorded
                            # outcome. Same prefix the redaction regex and
                            # canary_in_egress.yml both match on.
                            canary_leaked="MERIDIAN-CANARY-" in reply,
                        )
                    )
                    if delay_seconds:
                        time.sleep(delay_seconds)
    return replayed
