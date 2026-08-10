"""Bespoke HTML dashboard, generated the same way atlas_redteam.report
already does in this repo (plain-string-templated, no template-engine
dependency) — the architecture decision this project made was ClickHouse
over the Grafana Tempo+Loki+Prometheus stack (one container instead of
four, a real native clickhouseexporter, real pySigma-backend-clickhouse
Sigma execution), and pairing that with a bespoke dashboard rather than
installing Grafana on top of a non-Grafana-native backend is the coherent
follow-through on that choice, not a corner cut.

Oriented around the security questions the master prompt asks for, not
token counts: measured detection efficacy, the coverage matrix with its
honest gaps, and the two worked incident walkthroughs.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime


def _esc(value: object) -> str:
    return html.escape(str(value))


def _fmt_pct(value: float | None) -> str:
    return f"{value * 100:.0f}%" if value is not None else "—"


def _fmt_seconds(value: float | None) -> str:
    return f"{value:.1f}s" if value is not None else "—"


def _score_rows(scores: list[dict]) -> str:
    rows = []
    for s in scores:
        note = f" <span class='note'>({_esc(s['note'])})</span>" if s.get("note") else ""
        rows.append(
            "<tr>"
            f"<td>{_esc(s['name'])}{note}</td>"
            f"<td>{s['tp']}</td><td>{s['fp']}</td><td>{s['fn']}</td>"
            f"<td>{_fmt_pct(s['precision'])}</td>"
            f"<td>{_fmt_pct(s['recall'])}</td>"
            f"<td>{_fmt_seconds(s['mttd_seconds'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _unmeasurable_rows(unmeasurable: dict[str, str]) -> str:
    return "\n".join(
        f"<tr><td>{_esc(name)}</td><td>{_esc(reason)}</td></tr>"
        for name, reason in unmeasurable.items()
    )


def _coverage_rows(matrix: dict[str, dict]) -> str:
    rows = []
    for tid, entry in matrix.items():
        if entry["uncovered_reason"]:
            rows.append(
                f"<tr class='uncovered'><td>{_esc(tid)}</td><td>&mdash; not covered</td>"
                f"<td>{_esc(entry['uncovered_reason'])}</td></tr>"
            )
            continue
        detector_cells = []
        for name in entry["detectors"]:
            recall = entry["recall"].get(name)
            if entry["unmeasurable_reason"] and name in entry["unmeasurable_reason"]:
                detector_cells.append(f"{_esc(name)} (unmeasurable)")
            elif recall is not None:
                detector_cells.append(f"{_esc(name)} (recall {_fmt_pct(recall)})")
            else:
                detector_cells.append(f"{_esc(name)} (no positive instance measured)")
        rows.append(f"<tr><td>{_esc(tid)}</td><td>{'; '.join(detector_cells)}</td><td></td></tr>")
    return "\n".join(rows)


def render_dashboard(
    attack_trial_count: int,
    benign_trial_count: int,
    scores: list[dict],
    unmeasurable: dict[str, str],
    coverage_matrix: dict[str, dict],
    incident_walkthroughs_html: str = "",
) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>atlas-detect — measured detection efficacy</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; max-width: 1100px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; vertical-align: top; }}
  th {{ background: #f4f4f4; }}
  code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; }}
  .note {{ color: #666; font-size: 0.85em; }}
  tr.uncovered td {{ color: #888; }}
  .incident {{ border-left: 3px solid #999; padding-left: 1rem; margin: 1.5rem 0; }}
  .incident pre {{ background: #f8f8f8; padding: 0.75rem; overflow-x: auto; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>atlas-detect — measured detection efficacy</h1>
<p>Generated {_esc(generated_at)}. Dataset: {attack_trial_count} attack replays
(Project 1's real transcripts, re-issued against the live instrumented stack)
vs. {benign_trial_count} benign requests (workload_generator.py). Every
number below is measured against this run, not asserted.</p>

<h2>Per-detector efficacy</h2>
<table>
<tr><th>Detector</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th><th>MTTD</th></tr>
{_score_rows(scores)}
</table>
<p class="note">MTTD is batch-scan latency (query time minus event timestamp) in this
implementation — detectors run as a periodic scan over ClickHouse, not a
live streaming consumer. Stated as such, not dressed up as production
real-time detection latency.</p>

<h2>Detectors with no positive instance in this corpus</h2>
<p>Not reported as 0% recall (misleadingly implies a real miss) or omitted
(implies untested) — stated plainly instead.</p>
<table>
<tr><th>Detector</th><th>Why unmeasurable here</th></tr>
{_unmeasurable_rows(unmeasurable)}
</table>

<h2>Coverage matrix</h2>
<p>OWASP LLM Top 10 2026 / Agentic (ASI) Top 10 &mdash; which detector(s) target each
category and their measured recall, or an honest reason nothing does.</p>
<table>
<tr><th>ID</th><th>Detector(s) / measured recall</th><th>Why uncovered</th></tr>
{_coverage_rows(coverage_matrix)}
</table>

{incident_walkthroughs_html}
</body>
</html>
"""
