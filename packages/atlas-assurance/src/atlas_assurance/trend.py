"""Control effectiveness / ASR trend across real committed builds.

Built directly from `evidence/findings.duckdb`'s real run history — the
`phase_a_*` (before-control) → `phase_c_*` (after-control) pairs Projects
2 and 3 already committed are genuine, independently-timestamped builds,
not synthesized for this view.

Honest scoping: this pipeline's evidence store only carries each
control's *current* test result, not a historical log of past pass/fail
states — so "control effectiveness over time" here is necessarily built
from Finding-level ASR history (which genuinely is tracked, per run),
not from a fabricated history of test outcomes the pipeline never
recorded. Stated here rather than silently implied.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from atlas_schema import Finding


@dataclass(frozen=True)
class TrendPoint:
    run_id: str
    timestamp: str
    taxonomy_id: str
    probe_id: str
    status: str
    asr: float
    asr_ci_low: float
    asr_ci_high: float


def build_trend(findings: list[Finding]) -> list[TrendPoint]:
    points = [
        TrendPoint(
            run_id=f.run_id,
            timestamp=f.timestamp.isoformat(),
            taxonomy_id=t.id,
            probe_id=f.probe_id,
            status=f.status.value,
            asr=f.asr,
            asr_ci_low=f.asr_ci_low,
            asr_ci_high=f.asr_ci_high,
        )
        for f in findings
        for t in f.taxonomy
    ]
    return sorted(points, key=lambda p: (p.taxonomy_id, p.timestamp))


def group_by_taxonomy(points: list[TrendPoint]) -> dict[str, list[TrendPoint]]:
    grouped: dict[str, list[TrendPoint]] = {}
    for p in points:
        grouped.setdefault(p.taxonomy_id, []).append(p)
    return grouped


def _esc(value: object) -> str:
    return html.escape(str(value))


def render_trend_report(points: list[TrendPoint]) -> str:
    grouped = group_by_taxonomy(points)
    sections = []
    for taxonomy_id in sorted(grouped):
        rows = "\n".join(
            f"<tr><td>{_esc(p.run_id)}</td><td>{_esc(p.timestamp)}</td><td>{_esc(p.probe_id)}</td>"
            f"<td>{_esc(p.status)}</td><td>{p.asr:.3f}</td>"
            f"<td>[{p.asr_ci_low:.3f}, {p.asr_ci_high:.3f}]</td></tr>"
            for p in grouped[taxonomy_id]
        )
        sections.append(
            f"<h3>{_esc(taxonomy_id)}</h3>\n<table>\n"
            "<tr><th>Run</th><th>Timestamp</th><th>Probe</th><th>Status</th><th>ASR</th><th>95% CI</th></tr>\n"
            f"{rows}\n</table>"
        )
    body = "\n".join(sections)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>atlas-assurance — ASR trend across builds</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; max-width: 1000px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.6rem; text-align: left; font-size: 0.85rem; }}
  th {{ background: #f4f4f4; }}
</style>
</head>
<body>
<h1>atlas-assurance — ASR trend across builds</h1>
<p>Per-taxonomy attack success rate across every real committed run in
<code>evidence/findings.duckdb</code>, ordered by timestamp. This is built from
Finding-level history, not a historical log of control test outcomes — see
this module's docstring for why.</p>
{body}
</body>
</html>
"""
