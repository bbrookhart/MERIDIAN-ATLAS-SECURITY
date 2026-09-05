"""Canonical OWASP taxonomy tables for the whole portfolio.

These live in `atlas-schema` — alongside `Finding`, the other shared
contract — rather than in any one project, because four packages need
the ID→name mapping and only one of them has any business depending on
the red-team toolchain.

That's not a hypothetical: `atlas-assurance` previously imported this
table from `atlas_redteam.coverage`, which made garak, PyRIT and deepteam
(and, through PyRIT, the whole torch/transformers tree) hard runtime
dependencies of the assurance pipeline — to read a twenty-entry dict of
strings. `atlas-detect`'s README documents that same dependency-boundary
mistake as a bug it found and fixed via `docker build` failures; this
module is the structural fix so it can't recur.

IDs follow the OWASP Top 10 for LLM Applications 2026 and the OWASP Top
10 for Agentic Applications (ASI) 2026. Both are living documents —
re-verify against https://genai.owasp.org before citing either set in an
external report.
"""

from __future__ import annotations

from typing import Final

LLM_CATEGORIES: Final[dict[str, str]] = {
    "LLM01:2026": "Prompt Injection",
    "LLM02:2026": "Sensitive Information Disclosure",
    "LLM03:2026": "Excessive Agency",
    "LLM04:2026": "Supply Chain",
    "LLM05:2026": "Data and Model Poisoning",
    "LLM06:2026": "Unbounded Consumption",
    "LLM07:2026": "Misinformation",
    "LLM08:2026": "Hidden Context Exposure",
    "LLM09:2026": "Vector and Embedding Weaknesses",
    "LLM10:2026": "Improper Output Handling",
}

ASI_CATEGORIES: Final[dict[str, str]] = {
    "ASI01": "Agent Goal Hijack",
    "ASI02": "Tool Misuse & Exploitation",
    "ASI03": "Agent Identity & Privilege Abuse",
    "ASI04": "Agentic Supply Chain Compromise",
    "ASI05": "Unexpected Code Execution",
    "ASI06": "Memory & Context Poisoning",
    "ASI07": "Insecure Inter-Agent Communication",
    "ASI08": "Cascading Agent Failures",
    "ASI09": "Human-Agent Trust Exploitation",
    "ASI10": "Rogue Agents",
}

ALL_CATEGORIES: Final[dict[str, str]] = {**LLM_CATEGORIES, **ASI_CATEGORIES}

__all__ = ["ALL_CATEGORIES", "ASI_CATEGORIES", "LLM_CATEGORIES"]
