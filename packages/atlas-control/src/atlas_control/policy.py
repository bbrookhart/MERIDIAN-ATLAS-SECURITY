"""OPA-backed policy evaluation — policy as code, outside the model.

Every tool invocation is authorized here, via a subprocess call to the real
`opa` binary evaluating packages/atlas-control/policy/tool_authorization.rego
against a JSON input document. There is no code path by which conversation
content reaches this decision.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from atlas_detect.semconv import (
    ATTR_ATLAS_POLICY_ALLOW,
    ATTR_ATLAS_POLICY_RULE,
    ATTR_ATLAS_POLICY_TOOL,
    ATTR_ATLAS_ROLE,
)

from atlas_control.config import settings
from atlas_control.telemetry import tracer


class PolicyEngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorizationRequest:
    role: str
    session_id: str
    tool: str
    args: dict
    tool_calls_used: int
    refund_cents_used: int


@dataclass(frozen=True)
class AuthorizationResult:
    allow: bool
    reason: str


def _opa_binary() -> str:
    binary = shutil.which("opa")
    if not binary:
        raise PolicyEngineError("opa binary not found on PATH")
    return binary


def _build_input(request: AuthorizationRequest) -> dict:
    return {
        "caller": {"role": request.role, "session_id": request.session_id},
        "tool": request.tool,
        "args": request.args,
        "budget": {
            "tool_calls_used": request.tool_calls_used,
            "refund_cents_used": request.refund_cents_used,
        },
        "limits": {
            "max_tool_calls_per_session": settings.max_tool_calls_per_session,
            "max_refund_cents_per_session": settings.max_refund_cents_per_session,
        },
    }


def authorize(request: AuthorizationRequest, policy_dir: Path | None = None) -> AuthorizationResult:
    with tracer.start_as_current_span("policy_decision.tool") as span:
        span.set_attribute(ATTR_ATLAS_ROLE, request.role)
        span.set_attribute(ATTR_ATLAS_POLICY_TOOL, request.tool)

        policy_dir = policy_dir or settings.policy_dir
        input_doc = _build_input(request)

        result = subprocess.run(
            [
                _opa_binary(),
                "eval",
                "-d",
                str(policy_dir),
                "-I",
                "-f",
                "json",
                "data.atlas.authz",
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

        authz_result = AuthorizationResult(
            allow=bool(value.get("allow", False)), reason=value.get("reason", "denied")
        )
        span.set_attribute(ATTR_ATLAS_POLICY_ALLOW, authz_result.allow)
        span.set_attribute(ATTR_ATLAS_POLICY_RULE, authz_result.reason)
        return authz_result
