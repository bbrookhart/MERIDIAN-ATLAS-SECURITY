"""Capability tokens: per-invocation, short-TTL, single-tool,
argument-scoped credentials — replacing Atlas's one long-lived
`TOOL_CREDENTIAL` shared across every tool.

Leaking today's `TOOL_CREDENTIAL` authorizes every tool, forever. Leaking
one capability token authorizes exactly one already-policy-approved call to
one tool with one specific argument set, for `capability_ttl_seconds`
(default 30s), and only once (each `jti` is single-use).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass

import jwt

from atlas_control.config import settings

ALGORITHM = "HS256"


def _canonical_args_hash(args: dict) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class Capability:
    tool: str
    args_hash: str
    session_id: str
    jti: str
    exp: int


def mint(tool: str, args: dict, session_id: str) -> str:
    """Mint a capability token. Only ever called after policy.authorize()
    has already approved this exact tool+args+session — minting is not
    itself an authorization decision.
    """
    now = int(time.time())
    claims = {
        "tool": tool,
        "args_hash": _canonical_args_hash(args),
        "session_id": session_id,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + settings.capability_ttl_seconds,
    }
    return jwt.encode(claims, settings.capability_signing_key, algorithm=ALGORITHM)


class CapabilityError(Exception):
    pass


_redeemed_jtis: set[str] = set()


def redeem(token: str, tool: str, args: dict, session_id: str) -> Capability:
    """Verify and consume a capability token for one specific invocation.

    Raises CapabilityError if the token is expired, malformed, already
    redeemed, or scoped to a different tool/args/session than requested —
    a token minted for `issue_refund` with amount_cents=40000 cannot be
    replayed against `issue_refund` with amount_cents=5000000, and cannot
    be redeemed twice.
    """
    try:
        claims = jwt.decode(token, settings.capability_signing_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise CapabilityError("capability token expired") from e
    except jwt.InvalidTokenError as e:
        raise CapabilityError(f"invalid capability token: {e}") from e

    if claims["jti"] in _redeemed_jtis:
        raise CapabilityError("capability token already redeemed")
    if claims["tool"] != tool:
        raise CapabilityError("capability token scoped to a different tool")
    if claims["session_id"] != session_id:
        raise CapabilityError("capability token scoped to a different session")
    if claims["args_hash"] != _canonical_args_hash(args):
        raise CapabilityError("capability token scoped to different arguments")

    _redeemed_jtis.add(claims["jti"])
    return Capability(
        tool=claims["tool"],
        args_hash=claims["args_hash"],
        session_id=claims["session_id"],
        jti=claims["jti"],
        exp=claims["exp"],
    )
