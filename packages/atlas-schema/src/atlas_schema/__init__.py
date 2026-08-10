"""Shared finding schema for the Meridian Atlas security portfolio."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator

SCHEMA_VERSION = "1.0.0"


class TaxonomyFramework(str, Enum):
    OWASP_LLM_2026 = "owasp_llm_2026"
    OWASP_ASI_2026 = "owasp_asi_2026"
    OWASP_MCP = "owasp_mcp"
    MITRE_ATLAS = "mitre_atlas"


class FindingStatus(str, Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    REGRESSED = "regressed"


class TaxonomyRef(BaseModel):
    framework: TaxonomyFramework
    id: str


class Finding(BaseModel):
    finding_id: str
    run_id: str
    timestamp: datetime
    target_build_sha: str
    tool: str
    tool_version: str
    probe_id: str
    taxonomy: list[TaxonomyRef]
    attempts: int
    successes: int
    asr: float
    asr_ci_low: float
    asr_ci_high: float
    ci_method: str = "wilson"
    seed: int | None
    evidence_path: str | None
    repro_command: str
    status: FindingStatus
    control_ref: str | None
    retest_run_id: str | None

    @model_validator(mode="after")
    def _check_attempts_bounds(self) -> Finding:
        if not (0 <= self.successes <= self.attempts):
            raise ValueError(
                f"successes ({self.successes}) must be between 0 and attempts ({self.attempts})"
            )
        return self

    @model_validator(mode="after")
    def _check_ci_bounds(self) -> Finding:
        if not (self.asr_ci_low <= self.asr <= self.asr_ci_high):
            raise ValueError(
                f"asr ({self.asr}) must fall within [asr_ci_low={self.asr_ci_low}, "
                f"asr_ci_high={self.asr_ci_high}]"
            )
        return self

    @property
    def determinism_class(self) -> str:
        if self.asr > 0.95:
            return "deterministic"
        ci_width = self.asr_ci_high - self.asr_ci_low
        if self.asr < 0.05 and ci_width > 0.2:
            return "flaky"
        return "probabilistic"


__all__ = [
    "SCHEMA_VERSION",
    "Finding",
    "FindingStatus",
    "TaxonomyFramework",
    "TaxonomyRef",
]
