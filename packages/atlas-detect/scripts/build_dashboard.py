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
OUT_PATH = REPO_ROOT / "evidence" / "reports" / "atlas_detect_dashboard.html"

INCIDENT_LOGS = {
    "Incident 1: detected exfiltration attempt": "/tmp/incident_exfil3.log",
    "Incident 2: detected goal hijack attempt": "/tmp/incident_hijack2.log",
}


def _incident_html() -> str:
    sections = ["<h2>Incident walkthroughs</h2>"]
    for title, log_path in INCIDENT_LOGS.items():
        text = Path(log_path).read_text()
        sections.append(
            f'<div class="incident"><h3>{html.escape(title)}</h3><pre>{html.escape(text)}</pre></div>'
        )
    return "\n".join(sections)


def main() -> None:
    data = json.loads(RESULTS_PATH.read_text())
    dashboard_html = render_dashboard(
        attack_trial_count=data["attack_trial_count"],
        benign_trial_count=data["benign_trial_count"],
        scores=data["scores"],
        unmeasurable=data["unmeasurable"],
        coverage_matrix=data["coverage_matrix"],
        incident_walkthroughs_html=_incident_html(),
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(dashboard_html)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
