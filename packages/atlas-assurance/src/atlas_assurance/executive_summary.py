"""One-page executive summary — business language, generated entirely
from the register's own data (never a second hand-written narrative that
could drift from it). Top 3 residual risks come straight from
`business_translation_top5`, sliced to 3; "what changed" diffs this
register against a previously generated one, if given.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from atlas_schema.taxonomy import ALL_CATEGORIES


def _esc(value: object) -> str:
    return html.escape(str(value))


def _risk_posture(register: dict) -> str:
    total = len(register["controls"])
    stale = register["controls_stale"]
    not_assessed = register["controls_not_assessed"]
    gaps = len(register["coverage_gaps"])
    posture = "in good standing" if (stale == 0 and not_assessed == 0) else "degraded"
    return (
        f"{total} controls are registered against Atlas. {register['controls_assessed']} carry "
        f"real, currently-passing evidence; {stale} are stale (evidence exists but is failing or "
        f"older than its own max-age); {not_assessed} have no linked evidence at all. "
        f"{gaps} of {len(ALL_CATEGORIES)} OWASP LLM/ASI categories have a coverage gap. "
        f"Overall posture: {posture}."
    )


def _diff_since(new: dict, old: dict) -> list[str]:
    changes: list[str] = []
    old_by_id = {c["control_id"]: c for c in old["controls"]}
    new_by_id = {c["control_id"]: c for c in new["controls"]}

    for control_id, new_row in new_by_id.items():
        old_row = old_by_id.get(control_id)
        if old_row is None:
            changes.append(f"new control registered: {control_id}")
            continue
        if old_row["status"] != new_row["status"]:
            changes.append(f"{control_id}: status {old_row['status']} → {new_row['status']}")
        elif old_row.get("freshness") != new_row.get("freshness"):
            changes.append(
                f"{control_id}: freshness {old_row.get('freshness')} → {new_row.get('freshness')}"
            )
    for control_id in set(old_by_id) - set(new_by_id):
        changes.append(f"control removed from registry: {control_id}")

    old_gaps = {g["taxonomy_id"] for g in old["coverage_gaps"]}
    new_gaps = {g["taxonomy_id"] for g in new["coverage_gaps"]}
    for taxonomy_id in sorted(new_gaps - old_gaps):
        changes.append(f"new coverage gap: {taxonomy_id}")
    for taxonomy_id in sorted(old_gaps - new_gaps):
        changes.append(f"coverage gap closed: {taxonomy_id}")

    return changes or [
        "No control status, freshness, or coverage-gap changes since the last report."
    ]


def render_executive_summary(register: dict, previous_register: dict | None = None) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    top3 = register["business_translation_top5"][:3]

    if previous_register is None:
        changes = ["First generated report — no previous register to compare against."]
    else:
        changes = _diff_since(register, previous_register)

    top3_html = "\n".join(
        f"""<div class="risk">
<h3>#{i} — {_esc(t["technical_finding"])} (AIVSS {t["aivss_score"]:.2f})</h3>
<p><strong>What an attacker achieves:</strong> {_esc(t["attacker_achieves"])}</p>
<p><strong>Business impact:</strong> {_esc(t["business_impact_insurer"])}</p>
<p><strong>Control:</strong> {_esc(", ".join(t["control_names"])) if t["control_names"] else "none linked"}</p>
<p><strong>Residual risk:</strong> {_esc(t["residual_risk"])}</p>
</div>"""
        for i, t in enumerate(top3, start=1)
    )
    changes_html = "\n".join(f"<li>{_esc(c)}</li>" for c in changes)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>atlas-assurance — executive summary</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; max-width: 850px; line-height: 1.5; }}
  .risk {{ border-left: 3px solid #999; padding-left: 1rem; margin: 1.5rem 0; }}
  .note {{ color: #666; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>atlas-assurance — executive summary</h1>
<p class="note">Generated {_esc(generated_at)}. Every figure below is read from the machine-readable
control register, not restated by hand — crosswalks and evidence only, no compliance claims.</p>

<h2>Risk posture</h2>
<p>{_risk_posture(register)}</p>

<h2>Top 3 residual risks</h2>
{top3_html}

<h2>What changed since the last report</h2>
<ul>
{changes_html}
</ul>
</body>
</html>
"""
