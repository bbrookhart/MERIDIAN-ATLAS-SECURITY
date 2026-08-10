"""Regenerates the AI-BOM and diffs it (normalized — see
`bom.normalize_for_drift_check`) against the last-committed
`evidence/assurance/atlas_ai_bom.json`. Exits non-zero on unexpected
drift, wired into `.github/workflows/atlas-assurance.yml` as the
LLM04:2026 supply-chain control this project's registry.py asserts is
tested.

    uv run --package atlas-assurance python packages/atlas-assurance/scripts/check_bom_drift.py
"""

from __future__ import annotations

import json
import sys

from atlas_assurance.bom import REPO_ROOT, build_bom, emit_cyclonedx_json, normalize_for_drift_check

COMMITTED_BOM_PATH = REPO_ROOT / "evidence" / "assurance" / "atlas_ai_bom.json"


def main() -> int:
    bom_json_str = emit_cyclonedx_json(build_bom())
    new_bom = json.loads(bom_json_str)

    if not COMMITTED_BOM_PATH.exists():
        COMMITTED_BOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        COMMITTED_BOM_PATH.write_text(bom_json_str)
        print(f"No committed BOM found — wrote initial baseline to {COMMITTED_BOM_PATH}")
        return 0

    old_bom = json.loads(COMMITTED_BOM_PATH.read_text())
    old_snapshot = normalize_for_drift_check(old_bom)
    new_snapshot = normalize_for_drift_check(new_bom)

    if old_snapshot == new_snapshot:
        print(f"BOM drift check passed — no inventory change vs. {COMMITTED_BOM_PATH}")
        return 0

    added_components = set(new_snapshot["components"]) - set(old_snapshot["components"])
    removed_components = set(old_snapshot["components"]) - set(new_snapshot["components"])
    added_services = set(new_snapshot["services"]) - set(old_snapshot["services"])
    removed_services = set(old_snapshot["services"]) - set(new_snapshot["services"])

    print("BOM DRIFT DETECTED vs. the committed baseline:")
    for c in sorted(added_components):
        print(f"  + component {c}")
    for c in sorted(removed_components):
        print(f"  - component {c}")
    for s in sorted(added_services):
        print(f"  + service {s}")
    for s in sorted(removed_services):
        print(f"  - service {s}")
    print(
        f"\nThis script does not overwrite the committed baseline on drift — that's a "
        f"deliberate choice a human should make. If this change is expected, regenerate "
        f"it deliberately: `rm {COMMITTED_BOM_PATH} && uv run --package atlas-assurance "
        f"python packages/atlas-assurance/scripts/check_bom_drift.py`, then commit the result."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
