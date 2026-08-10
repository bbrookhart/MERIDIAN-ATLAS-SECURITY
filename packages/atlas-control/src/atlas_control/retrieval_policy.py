"""OPA-backed retrieval authorization (Project 2) — the same policy engine
Project 3 built for tool execution (policy.py), evaluating a separate
policy file (policy/retrieval_authorization.rego) via the same subprocess
`opa eval` pattern. Kept as a separate module rather than overloading
policy.py: tool authorization and retrieval authorization are different
decisions with different input shapes, and this project's own thesis is
that a control's boundaries should be explicit, not implicit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from atlas_detect.semconv import ATTR_ATLAS_POLICY_ALLOW, ATTR_ATLAS_ROLE

from atlas_control.config import settings
from atlas_control.policy import PolicyEngineError
from atlas_control.telemetry import tracer


@dataclass(frozen=True)
class RetrievalAuthzResult:
    visible_roles: list[str]
    decisions: list[dict]


def _opa_binary() -> str:
    binary = shutil.which("opa")
    if not binary:
        raise PolicyEngineError("opa binary not found on PATH")
    return binary


def authorize_retrieval(
    role: str, chunks: list[dict] | None = None, policy_dir: Path | None = None
) -> RetrievalAuthzResult:
    with tracer.start_as_current_span("policy_decision.retrieval") as span:
        span.set_attribute(ATTR_ATLAS_ROLE, role)
        span.set_attribute("atlas.policy.mode", "post" if chunks else "pre")

        policy_dir = policy_dir or settings.policy_dir
        input_doc = {"caller": {"role": role}, "chunks": chunks or []}

        result = subprocess.run(
            [
                _opa_binary(),
                "eval",
                "-d",
                str(policy_dir),
                "-I",
                "-f",
                "json",
                "data.atlas.retrieval_authz",
            ],
            input=json.dumps(input_doc),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            raise PolicyEngineError(f"opa eval failed: {result.stderr or result.stdout}")

        payload = json.loads(result.stdout)
        try:
            value = payload["result"][0]["expressions"][0]["value"]
        except (KeyError, IndexError) as e:
            raise PolicyEngineError(f"unexpected opa eval output shape: {payload}") from e

        authz_result = RetrievalAuthzResult(
            visible_roles=sorted(value.get("visible_roles", [])),
            decisions=value.get("decisions", []),
        )
        denied = [d for d in authz_result.decisions if not d.get("allow", True)]
        span.set_attribute(ATTR_ATLAS_POLICY_ALLOW, len(denied) == 0)
        span.set_attribute("atlas.policy.denied_count", len(denied))
        return authz_result
