"""Builds evidence/reports/atlas_detect_dashboard.html from
phase3_results.json and the two incident walkthrough logs — the same
"generate a committed HTML report as evidence" pattern atlas_redteam.report
already established in this repo.

    uv run --package atlas-detect python packages/atlas-detect/scripts/build_dashboard.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from atlas_detect.dashboard import render_dashboard

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[2]
RESULTS_PATH = SCRIPTS_DIR / "phase3_results.json"
POST_RESULTS_PATH = SCRIPTS_DIR / "phase3_results_post.json"
OUT_PATH = REPO_ROOT / "evidence" / "reports" / "atlas_detect_dashboard.html"

# Committed under evidence/, not read from /tmp: the incident walkthroughs
# are evidence, and a dashboard that can only be regenerated on the one
# machine where the scripts last ran isn't reproducible. Both logs were
# checked to contain no raw canary value before committing — the
# exfiltration log shows `[REDACTED-CANARY]`, which is the Collector's
# flag-then-redact behaviour working.
INCIDENT_LOGS = {
    "Incident 1: detected exfiltration attempt": REPO_ROOT
    / "evidence"
    / "incidents"
    / "detected_exfiltration.log",
    "Incident 2: detected goal hijack attempt": REPO_ROOT
    / "evidence"
    / "incidents"
    / "detected_goal_hijack.log",
}


def _incident_html() -> str:
    sections = ["<h2>Incident walkthroughs</h2>"]
    for title, log_path in INCIDENT_LOGS.items():
        if not Path(log_path).exists():
            sections.append(
                f'<div class="incident"><h3>{html.escape(title)}</h3>'
                f"<p class='note'>Log not found at {html.escape(str(log_path))} — "
                "rerun the walkthrough script to regenerate it.</p></div>"
            )
            continue
        text = Path(log_path).read_text()
        sections.append(
            f'<div class="incident"><h3>{html.escape(title)}</h3><pre>{html.escape(text)}</pre></div>'
        )
    return "\n".join(sections)


def main() -> None:
    data = json.loads(RESULTS_PATH.read_text())
    post = json.loads(POST_RESULTS_PATH.read_text()) if POST_RESULTS_PATH.exists() else None
    dashboard_html = render_dashboard(
        attack_trial_count=data["attack_trial_count"],
        benign_trial_count=data["benign_trial_count"],
        scores=data["scores"],
        unmeasurable=data["unmeasurable"],
        coverage_matrix=data["coverage_matrix"],
        incident_walkthroughs_html=_incident_html(),
        post_mode=post,
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(dashboard_html)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
