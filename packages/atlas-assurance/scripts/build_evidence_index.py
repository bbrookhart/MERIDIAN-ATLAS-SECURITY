"""Builds evidence/reports/index.html — the landing page for the published
evidence site (GitHub Pages).

Every report in this repo is a real generated artifact, but on GitHub they
render as raw HTML source, so in practice nobody sees them. This index is
what makes them reachable: one page, grouped by what they prove, linking
to the actual rendered reports.

Finding counts are read from the real `evidence/findings.duckdb` rather
than typed in, so this page cannot drift from the database the way a
hand-written index would. The one-line descriptions are hand-authored
context — the same category of input as `registry.py`'s control
descriptions.

    uv run --package atlas-assurance python packages/atlas-assurance/scripts/build_evidence_index.py
"""

from __future__ import annotations

import html
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from atlas_assurance.ingest.findings import load_findings

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = REPO_ROOT / "evidence" / "reports"
OUT_PATH = REPORTS_DIR / "index.html"

# (filename, title, what it proves). Ordered as a reviewer should read them.
_RED_TEAM = [
    (
        "phase_a_agent_baseline.html",
        "Phase A — agent surface, before controls",
        (
            "The original attack run against the unprotected agent. Refund-threshold bypass "
            "succeeded at 0.600 ASR, cross-session memory leak at 0.200."
        ),
    ),
    (
        "phase_a_rag_authorization.html",
        "Phase A — retrieval surface, before controls",
        "Broker asking directly for HR documents succeeded at 1.000 ASR, deterministic.",
    ),
    (
        "phase_c_agent_baseline.html",
        "Phase C — agent surface, after controls",
        "Same probes re-run against the hardened agent once atlas-control was enforcing.",
    ),
    (
        "phase_c_rag_authorization.html",
        "Phase C — retrieval surface, after controls",
        "Same probes re-run once per-role retrieval authorization was enforcing.",
    ),
    (
        "phase_c_highn.html",
        "Phase C — agent retest at N=20",
        (
            "Higher trial count, because zero successes at N=5 only bounds ASR below 0.434 — "
            "not strong enough to call a fix. This is the run the headline numbers cite."
        ),
    ),
    (
        "phase_c_rag_highn.html",
        "Phase C — retrieval retest at N=20",
        "The N=20 retest backing the LLM02:2026 before/after claim.",
    ),
    (
        "run_a4196b539408.html",
        "Multi-tool exploratory run",
        (
            "PyRIT, garak and deepteam together against the chat surface — the run that "
            "showed deepteam's excessive-agency probe never reproduced the vulnerability."
        ),
    ),
]

_DETECTION = [
    (
        "atlas_detect_dashboard.html",
        "Detection efficacy — measured, both retrieval modes",
        (
            "Per-detector TP/FP/FN, precision, recall and MTTD from replaying the real attack "
            "corpus against the live instrumented stack, plus the two worked incident "
            "walkthroughs with real timestamps."
        ),
    ),
]

_ASSURANCE = [
    (
        "atlas_assurance_report.html",
        "Control register & evidence",
        (
            "Every control linked to the test that exercises it, with freshness. The pipeline "
            "refuses to assert a control is effective without a linked passing test."
        ),
    ),
    (
        "atlas_assurance_executive_summary.html",
        "Executive summary",
        (
            "The same register in business language: risk posture, top residual risks, and "
            "what changed since the previous report."
        ),
    ),
    (
        "atlas_assurance_trend.html",
        "Attack success rate over time",
        "Per-taxonomy ASR across every committed run, before and after each control.",
    ),
]


def _esc(value: object) -> str:
    return html.escape(str(value))


def _cards(entries: list[tuple[str, str, str]], counts: Counter[str]) -> str:
    cards = []
    for filename, title, description in entries:
        if not (REPORTS_DIR / filename).exists():
            continue
        run_id = filename.removesuffix(".html")
        n = counts.get(run_id)
        badge = f'<span class="badge">{n} findings</span>' if n else ""
        cards.append(
            f'<a class="card" href="{_esc(filename)}">'
            f"<h3>{_esc(title)}{badge}</h3>"
            f"<p>{_esc(description)}</p>"
            f'<span class="go">Open report &rarr;</span>'
            "</a>"
        )
    return "\n".join(cards)


def _repo_url() -> str:
    """Derived from the git remote rather than hardcoded, so this page can't
    point at the wrong account. Falls back to the GitHub search page if the
    repo has no remote yet."""
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "https://github.com"
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url.removeprefix("git@github.com:")
    return url.removesuffix(".git")


def main() -> None:
    counts = Counter(f.run_id for f in load_findings())
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    repo_url = _repo_url()

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>meridian-atlas-security — evidence</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    margin: 0; padding: 3rem 1.5rem; line-height: 1.6;
    background: #0d1117; color: #e6edf3;
  }}
  .wrap {{ max-width: 1000px; margin: 0 auto; }}
  header {{ border-bottom: 1px solid #30363d; padding-bottom: 2rem; margin-bottom: 2.5rem; }}
  h1 {{ font-size: 2rem; margin: 0 0 .5rem; letter-spacing: -0.02em; }}
  .tag {{ color: #7d8590; font-size: 1.05rem; margin: 0 0 1.25rem; }}
  .meta {{ color: #7d8590; font-size: .85rem; }}
  h2 {{ font-size: 1.1rem; text-transform: uppercase; letter-spacing: .08em;
       color: #7d8590; margin: 2.5rem 0 1rem; font-weight: 600; }}
  .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }}
  .card {{
    display: block; text-decoration: none; color: inherit;
    border: 1px solid #30363d; border-radius: 10px; padding: 1.25rem;
    background: #161b22; transition: border-color .15s, transform .15s;
  }}
  .card:hover {{ border-color: #58a6ff; transform: translateY(-2px); }}
  .card h3 {{ margin: 0 0 .5rem; font-size: 1rem; }}
  .card p {{ margin: 0 0 .75rem; color: #9198a1; font-size: .9rem; }}
  .go {{ color: #58a6ff; font-size: .85rem; font-weight: 600; }}
  .badge {{
    display: inline-block; margin-left: .5rem; padding: .1rem .5rem;
    border-radius: 999px; background: #1f6feb33; color: #58a6ff;
    font-size: .72rem; font-weight: 600; vertical-align: middle;
  }}
  .note {{
    border-left: 3px solid #d29922; background: #1c1a12; padding: 1rem 1.25rem;
    border-radius: 0 8px 8px 0; color: #d8d2c4; font-size: .9rem; margin-top: 2.5rem;
  }}
  a.home {{ color: #58a6ff; text-decoration: none; }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>meridian-atlas-security</h1>
  <p class="tag">Five surfaces of one AI system, attacked, controlled, retested and mapped to evidence.</p>
  <p class="meta">Every page below is a generated artifact, not a screenshot.
  Generated {_esc(generated_at)}. &nbsp;·&nbsp;
  <a class="home" href="{_esc(repo_url)}">Source on GitHub</a></p>
</header>

<h2>Red-team runs — before and after</h2>
<div class="grid">
{_cards(_RED_TEAM, counts)}
</div>

<h2>Detection</h2>
<div class="grid">
{_cards(_DETECTION, counts)}
</div>

<h2>Assurance</h2>
<div class="grid">
{_cards(_ASSURANCE, counts)}
</div>

<p class="note"><strong>This is a security lab.</strong> The target system
(<code>atlas</code>) is intentionally vulnerable and is documented as such.
Every attack here ran against a local instance; the red-team harness enforces a
target allowlist in code. All data is synthetic.</p>
</div>
</body>
</html>
"""
    OUT_PATH.write_text(page)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
