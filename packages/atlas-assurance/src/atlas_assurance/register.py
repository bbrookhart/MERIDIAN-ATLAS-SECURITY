"""Assembles the machine-readable control register — the one source of
truth every report in this package reads from (`report.py`,
`executive_summary.py`, `trend.py`). Nothing downstream recomputes a
number the register already has.

Detection efficacy is Project 4's own already-computed, already-committed
`phase3_results.json` — read verbatim, per this project's own "do not
re-derive" input contract. If that file isn't present (this project's
tests never bring up atlas-detect's live ClickHouse stack), the register
says so explicitly rather than omitting the section silently.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from atlas_redteam.coverage import ALL_CATEGORIES
from atlas_schema import Finding

from atlas_assurance.aivss import score_all, top_divergences
from atlas_assurance.business_translation import top_business_translations
from atlas_assurance.evidence_store import evidence_freshness, record_assertion
from atlas_assurance.models import ControlAssertion, TestResult, UnsupportedClaimError
from atlas_assurance.registry import CONTROLS, crosswalk_refs_for_control

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PHASE3_PATH = REPO_ROOT / "packages" / "atlas-detect" / "scripts" / "phase3_results.json"

SCHEMA_VERSION = "1.0.0"


def _try_assert(
    control, test_results: list[TestResult], findings: list[Finding], generated_at: datetime
) -> tuple[ControlAssertion | None, str | None]:
    try:
        return record_assertion(control, test_results, findings, generated_at), None
    except UnsupportedClaimError as e:
        return None, str(e)


def _control_row(
    control, assertion: ControlAssertion | None, error: str | None, generated_at: datetime
) -> dict:
    framework_refs = [
        {"framework": r.framework.value, "ref": r.ref} for r in crosswalk_refs_for_control(control)
    ]
    base = {
        "control_id": control.control_id,
        "name": control.name,
        "description": control.description,
        "control_ref": control.control_ref,
        "test_ref": control.test_ref,
        "max_age_days": control.max_age_days,
        "addresses_taxonomy": list(control.addresses_taxonomy),
        "framework_refs": framework_refs,
    }
    if assertion is None:
        return {
            **base,
            "status": "not_assessed",
            "passed": None,
            "freshness": None,
            "last_evidence_at": None,
            "finding_ids": [],
            "not_assessed_reason": error,
        }
    return {
        **base,
        "status": "assessed",
        "passed": assertion.test_result.passed,
        "freshness": evidence_freshness(assertion, generated_at),
        "last_evidence_at": assertion.test_result.timestamp.isoformat(),
        "finding_ids": list(assertion.finding_ids),
        "not_assessed_reason": None,
    }


def _coverage_gaps(control_rows: list[dict]) -> list[dict]:
    addressing: dict[str, list[str]] = {tid: [] for tid in ALL_CATEGORIES}
    fresh_addressing: dict[str, list[str]] = {tid: [] for tid in ALL_CATEGORIES}
    for row in control_rows:
        for tid in row["addresses_taxonomy"]:
            if tid not in addressing:
                continue
            addressing[tid].append(row["control_id"])
            if row["status"] == "assessed" and row["passed"] and row["freshness"] == "fresh":
                fresh_addressing[tid].append(row["control_id"])

    gaps = []
    for tid, name in ALL_CATEGORIES.items():
        if not addressing[tid]:
            gaps.append(
                {
                    "taxonomy_id": tid,
                    "name": name,
                    "reason": "no control in the registry addresses this category",
                }
            )
        elif not fresh_addressing[tid]:
            gaps.append(
                {
                    "taxonomy_id": tid,
                    "name": name,
                    "reason": (
                        f"controls exist ({', '.join(addressing[tid])}) but none currently have "
                        "fresh, passing evidence"
                    ),
                }
            )
    return gaps


def _load_detection_efficacy(path: Path) -> dict:
    if not path.exists():
        return {
            "available": False,
            "reason": (
                f"{path} not found — Project 4's phase3_results.json requires its live "
                "ClickHouse/Collector stack, which this build did not bring up"
            ),
        }
    return {
        "available": True,
        "source_path": str(path.relative_to(REPO_ROOT)),
        **json.loads(path.read_text()),
    }


def build_register(
    test_results: list[TestResult],
    findings: list[Finding],
    generated_at: datetime | None = None,
    phase3_path: Path = DEFAULT_PHASE3_PATH,
) -> dict:
    generated_at = generated_at or datetime.now(UTC)

    control_rows: list[dict] = []
    assertions_by_control_ref: dict[str, ControlAssertion] = {}
    assertions_by_taxonomy: dict[str, list[ControlAssertion]] = {}
    for control in CONTROLS:
        assertion, error = _try_assert(control, test_results, findings, generated_at)
        if assertion is not None:
            assertions_by_control_ref[control.control_ref] = assertion
            for taxonomy_id in control.addresses_taxonomy:
                assertions_by_taxonomy.setdefault(taxonomy_id, []).append(assertion)
        control_rows.append(_control_row(control, assertion, error, generated_at))

    aivss_results = score_all(findings)
    divergences = top_divergences(aivss_results, n=5)
    findings_by_id = {f.finding_id: f for f in findings}

    translations = top_business_translations(
        findings,
        aivss_results,
        assertions_by_control_ref,
        n=5,
        assertions_by_taxonomy=assertions_by_taxonomy,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "controls": control_rows,
        "controls_assessed": sum(1 for r in control_rows if r["status"] == "assessed"),
        "controls_not_assessed": sum(1 for r in control_rows if r["status"] == "not_assessed"),
        "controls_stale": sum(1 for r in control_rows if r.get("freshness") == "stale"),
        "aivss": {
            "findings_scored": len(aivss_results),
            "top_divergences": [
                {
                    "finding_id": d.finding_id,
                    "probe_id": findings_by_id[d.finding_id].probe_id,
                    "status": findings_by_id[d.finding_id].status.value,
                    "aivss_score": d.aivss_score,
                    "cvss_only_score": d.cvss_only_score,
                    "divergence": d.divergence,
                    "primary_metric": d.primary_metric,
                }
                for d in divergences
            ],
        },
        "coverage_gaps": _coverage_gaps(control_rows),
        "business_translation_top5": [asdict(t) for t in translations],
        "detection_efficacy": _load_detection_efficacy(phase3_path),
    }
