"""Coverage matrix: which OWASP 2026 categories this suite's probes reach.

The taxonomy tables themselves now live in `atlas_schema.taxonomy` (the
shared contract package) and are re-exported here so existing callers
keep working — see that module for why they moved. This module keeps only
what is genuinely red-team-specific: which categories need human
judgment, and how probes map onto categories.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas_schema.taxonomy import ALL_CATEGORIES, ASI_CATEGORIES, LLM_CATEGORIES

# Re-exported deliberately: callers (and this repo's own history) refer to
# these through atlas_redteam.coverage, so the move to atlas-schema stays
# source-compatible. Declared in __all__ so it reads as an intentional
# re-export rather than a dead import.
__all__ = [
    "ALL_CATEGORIES",
    "ASI_CATEGORIES",
    "LLM_CATEGORIES",
    "NEEDS_HUMAN_JUDGMENT",
    "CoverageRow",
    "build_coverage_matrix",
]

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
