"""Coverage matrix: which OWASP 2026 categories this suite's probes reach.

IDs and names follow the portfolio doc's own framework table (verified
against sources published within the week before this project started) —
both lists are living documents; re-verify against
https://genai.owasp.org before citing either ID set in an external report.
"""

from __future__ import annotations

from dataclasses import dataclass

LLM_CATEGORIES = {
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

ASI_CATEGORIES = {
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

ALL_CATEGORIES = {**LLM_CATEGORIES, **ASI_CATEGORIES}

# Per the portfolio doc: some categories need human judgment even when a
# probe nominally targets them — an automated pass/fail heuristic can't
# assess true sensitivity of a disclosure or the factual accuracy of a
# claim. Say so rather than claim full automated coverage.
NEEDS_HUMAN_JUDGMENT = {"LLM02:2026", "LLM07:2026"}


@dataclass
class CoverageRow:
    taxonomy_id: str
    name: str
    probe_ids: list[str]
    needs_human_judgment: bool

    @property
    def covered(self) -> bool:
        return len(self.probe_ids) > 0


def build_coverage_matrix(probe_taxonomy: dict[str, list[str]]) -> list[CoverageRow]:
    """probe_taxonomy: {probe_id: [taxonomy_id, ...]} from the suite definitions."""
    reached: dict[str, list[str]] = {cat: [] for cat in ALL_CATEGORIES}
    for probe_id, taxonomy_ids in probe_taxonomy.items():
        for tid in taxonomy_ids:
            if tid in reached:
                reached[tid].append(probe_id)

    return [
        CoverageRow(
            taxonomy_id=tid,
            name=ALL_CATEGORIES[tid],
            probe_ids=sorted(set(reached[tid])),
            needs_human_judgment=tid in NEEDS_HUMAN_JUDGMENT,
        )
        for tid in ALL_CATEGORIES
    ]
