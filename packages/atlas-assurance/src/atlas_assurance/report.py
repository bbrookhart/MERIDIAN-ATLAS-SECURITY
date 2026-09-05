"""Bespoke HTML assurance report — same plain-string-templating pattern
as `atlas_detect.dashboard` and `atlas_redteam.report` (no template-engine
dependency). Reads the register dict only; computes nothing of its own.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime


def _esc(value: object) -> str:
    return html.escape(str(value))


def _fmt_bool(value: bool | None) -> str:
    if value is None:
        return "—"
    return "yes" if value else "no"


def _control_rows(controls: list[dict]) -> str:
    # Stale and not-assessed controls first — evidence freshness is the
    # differentiating feature this project exists to surface, not bury.
    def sort_key(row: dict) -> tuple[int, str]:
        rank = {"not_assessed": 0, "stale": 1, "fresh": 2}
        return (rank.get(row["freshness"] or "not_assessed", 0), row["control_id"])

    rows = []
    for row in sorted(controls, key=sort_key):
        status_class = (
            "bad" if row["status"] == "not_assessed" or row["freshness"] == "stale" else "ok"
        )
        reason = (
            f" <span class='note'>({_esc(row['not_assessed_reason'])})</span>"
            if row["not_assessed_reason"]
            else ""
        )
        findings = ", ".join(row["finding_ids"]) or "—"
        rows.append(
            f"<tr class='{status_class}'>"
            f"<td>{_esc(row['control_id'])}<br><span class='note'>{_esc(row['name'])}</span></td>"
            f"<td>{_esc(row['status'])}{reason}</td>"
            f"<td>{_fmt_bool(row['passed'])}</td>"
            f"<td>{_esc(row['freshness'] or '—')}</td>"
            f"<td>{_esc(row['last_evidence_at'] or '—')}</td>"
            f"<td>{_esc(findings)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _divergence_rows(divergences: list[dict]) -> str:
    rows = []
    for d in divergences:
        rows.append(
            "<tr>"
            f"<td>{_esc(d['finding_id'])}</td>"
            f"<td>{_esc(d['probe_id'])}</td>"
            f"<td>{_esc(d['status'])}</td>"
            f"<td>{d['aivss_score']:.2f}</td>"
            f"<td>{d['cvss_only_score']:.2f}</td>"
            f"<td>{d['divergence']:+.2f}</td>"
            f"<td>{_esc(d['primary_metric'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _coverage_gap_rows(gaps: list[dict]) -> str:
    return "\n".join(
        f"<tr><td>{_esc(g['taxonomy_id'])}</td><td>{_esc(g['name'])}</td><td>{_esc(g['reason'])}</td></tr>"
        for g in gaps
    )


def _translation_rows(translations: list[dict]) -> str:
    rows = []
    for t in translations:
        control = (
            "<br>".join(_esc(name) for name in t["control_names"])
            if t["control_names"]
            else "<span class='note'>no control linked</span>"
        )
        rows.append(
            "<tr>"
            f"<td>{t['aivss_score']:.2f}</td>"
            f"<td>{_esc(t['technical_finding'])}</td>"
            f"<td>{_esc(t['attacker_achieves'])}</td>"
            f"<td>{_esc(t['business_impact_insurer'])}</td>"
            f"<td>{control}</td>"
            f"<td>{_esc(t['residual_risk'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _detection_efficacy_section(detection_efficacy: dict) -> str:
    if not detection_efficacy.get("available"):
        return f"<p class='note'>Not available in this build: {_esc(detection_efficacy.get('reason', ''))}</p>"
    rows = []
    for s in detection_efficacy.get("scores", []):
        precision = f"{s['precision'] * 100:.0f}%" if s.get("precision") is not None else "—"
        recall = f"{s['recall'] * 100:.0f}%" if s.get("recall") is not None else "—"
        rows.append(
            "<tr>"
            f"<td>{_esc(s['name'])}</td><td>{s['tp']}</td><td>{s['fp']}</td><td>{s['fn']}</td>"
            f"<td>{precision}</td><td>{recall}</td>"
            "</tr>"
        )
    return f"""<p>Source: <code>{_esc(detection_efficacy["source_path"])}</code>
(Project 4's own committed measurement — read verbatim, not recomputed here).</p>
<table>
<tr><th>Detector</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th></tr>
{"".join(rows)}
</table>"""


def render_assurance_report(register: dict) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>atlas-assurance — control register &amp; evidence</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; max-width: 1150px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; vertical-align: top; }}
  th {{ background: #f4f4f4; }}
  code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; }}
  .note {{ color: #666; font-size: 0.85em; }}
  tr.bad td {{ background: #fff4f4; }}
  tr.ok td {{ background: #f4fff6; }}
</style>
</head>
<body>
<h1>atlas-assurance — control register &amp; evidence</h1>
<p>Generated {_esc(generated_at)} from register generated {_esc(register["generated_at"])}.
{register["controls_assessed"]} controls assessed, {register["controls_not_assessed"]} not assessed,
{register["controls_stale"]} stale. Every row below links back to a real test result — no
assertion in this register exists without one (see evidence_store.py's enforcement).</p>

<h2>Control register</h2>
<p>Stale and not-assessed controls sorted first — evidence freshness is the point.</p>
<table>
<tr><th>Control</th><th>Status</th><th>Passed</th><th>Freshness</th><th>Last evidence</th><th>Findings mitigated</th></tr>
{_control_rows(register["controls"])}
</table>

<h2>AIVSS vs. plain CVSS — largest divergences</h2>
<p>{register["aivss"]["findings_scored"]} findings scored. See the README for why AIVSS,
faithfully ported from OWASP's real published v0.8 formula, scores <em>below</em> the CVSS-only
proxy for every finding in this corpus &mdash; a real, structural property of the published
formula, not a bug in this port.</p>
<table>
<tr><th>Finding</th><th>Probe</th><th>Status</th><th>AIVSS</th><th>CVSS-only</th><th>Divergence</th><th>Primary metric</th></tr>
{_divergence_rows(register["aivss"]["top_divergences"])}
</table>

<h2>Coverage gaps</h2>
<p>OWASP LLM Top 10 2026 / Agentic (ASI) Top 10 categories with no control, or no currently
fresh and passing control, in this registry.</p>
<table>
<tr><th>ID</th><th>Name</th><th>Reason</th></tr>
{_coverage_gap_rows(register["coverage_gaps"])}
</table>

<h2>Detection efficacy (Project 4)</h2>
{_detection_efficacy_section(register["detection_efficacy"])}

<h2>Business translation — top 5 findings by AIVSS score</h2>
<table>
<tr><th>AIVSS</th><th>Technical finding</th><th>Attacker achieves</th><th>Business impact (insurer)</th><th>Control</th><th>Residual risk</th></tr>
{_translation_rows(register["business_translation_top5"])}
</table>
</body>
</html>
"""
