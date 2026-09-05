"""Plain-string-templated HTML report — no new template-engine dependency."""

from __future__ import annotations

import html
from datetime import UTC, datetime

from atlas_schema import Finding

from atlas_redteam.coverage import CoverageRow


def _esc(value: object) -> str:
    return html.escape(str(value))


def _findings_rows(findings: list[Finding]) -> str:
    rows = []
    for f in findings:
        rows.append(
            f"<tr>"
            f"<td>{_esc(f.probe_id)}</td>"
            f"<td>{_esc(f.tool)}</td>"
            f"<td>{_esc(', '.join(t.id for t in f.taxonomy))}</td>"
            f"<td>{f.attempts}</td>"
            f"<td>{f.successes}</td>"
            f"<td>{f.asr:.3f} ({f.asr_ci_low:.3f}–{f.asr_ci_high:.3f})</td>"
            f"<td>{_esc(f.determinism_class)}</td>"
            f"<td>{_esc(f.status.value)}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _coverage_rows(coverage: list[CoverageRow]) -> str:
    rows = []
    for row in coverage:
        note = " (needs human judgment)" if row.needs_human_judgment else ""
        probes = ", ".join(row.probe_ids) if row.probe_ids else "— not covered"
        rows.append(
            f"<tr>"
            f"<td>{_esc(row.taxonomy_id)}</td>"
            f"<td>{_esc(row.name)}{_esc(note)}</td>"
            f"<td>{_esc(probes)}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def render_report(
    run_id: str,
    target_build_sha: str,
    findings: list[Finding],
    coverage: list[CoverageRow],
) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>atlas-redteam run {_esc(run_id)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f4f4f4; }}
  code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; }}
</style>
</head>
<body>
<h1>atlas-redteam run <code>{_esc(run_id)}</code></h1>
<p>Target build: <code>{_esc(target_build_sha)}</code> &mdash; generated {_esc(generated_at)}</p>

<h2>Findings</h2>
<table>
<tr><th>Probe</th><th>Tool</th><th>Taxonomy</th><th>Attempts</th><th>Successes</th>
<th>ASR (95% CI)</th><th>Class</th><th>Status</th></tr>
{_findings_rows(findings)}
</table>

<h2>Coverage matrix</h2>
<p>LLM Top 10 2026 / Agentic (ASI) Top 10 &mdash; which probes in this suite reach each category.</p>
<table>
<tr><th>ID</th><th>Category</th><th>Probes</th></tr>
{_coverage_rows(coverage)}
</table>
</body>
</html>
"""
