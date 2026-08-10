"""Shared types for the evidence pipeline.

The one rule this module exists to make impossible to violate silently:
a `ControlAssertion` cannot be constructed except through
`evidence_store.record_assertion()`, which requires a real, matched
`TestResult` — see that module's docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class UnsupportedClaimError(Exception):
    """Raised when a control assertion would have no linked, real evidence."""


@dataclass(frozen=True)
class TestResult:
    """One test outcome, ingested from a real CI-produced artifact —
    never hand-typed. `test_id` is namespaced by ingestion source so a
    pytest test and an `opa test` test can never collide:
    `"<package>::<classname>::<name>"` for pytest,
    `"opa::<rego package>::<name>"` for OPA.
    """

    __test__ = False  # tell pytest this dataclass isn't a test case despite the name

    test_id: str
    passed: bool
    timestamp: datetime
    duration_s: float
    source: str  # "pytest" | "opa"


class Framework(str, Enum):
    NIST_AI_RMF = "nist_ai_rmf"
    NIST_AI_600_1 = "nist_ai_600_1"
    ISO_42001 = "iso_42001"
    CSA_AICM = "csa_aicm"
    MITRE_ATLAS = "mitre_atlas"
    EU_AI_ACT = "eu_ai_act"


@dataclass(frozen=True)
class FrameworkRef:
    framework: Framework
    ref: str  # e.g. "Govern", "A.6 — AI system life cycle", "Art. 15"
    note: str = ""


@dataclass(frozen=True)
class ControlDef:
    """The one hand-authored input in this pipeline (see registry.py).
    Everything else — whether it's actually passing, when it last passed,
    whether it's stale — is computed from real ingested artifacts.
    """

    control_id: str
    name: str
    description: str
    control_ref: str
    test_ref: str
    max_age_days: int
    addresses_taxonomy: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlAssertion:
    control: ControlDef
    test_result: TestResult
    finding_ids: tuple[str, ...]
    generated_at: datetime = field(compare=False)


Freshness = str  # "fresh" | "stale" | "not_assessed"
