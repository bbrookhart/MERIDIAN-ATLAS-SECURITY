"""atlas-redteam CLI: run / baseline / check-regression."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from atlas_redteam import runner
from atlas_redteam.baseline import (
    baseline_from_findings,
    check_regression,
    load_baseline,
    save_baseline,
)
from atlas_redteam.coverage import build_coverage_matrix
from atlas_redteam.report import render_report
from atlas_redteam.store import DEFAULT_DB_PATH, FindingsStore
from atlas_redteam.target import AtlasClient, DisallowedTargetError

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SUITES_DIR = Path(__file__).resolve().parents[2] / "suites"
DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[2] / "baseline.json"
DEFAULT_REPORTS_DIR = REPO_ROOT / "evidence" / "reports"


def cmd_run(args: argparse.Namespace) -> int:
    try:
        target = AtlasClient(args.target, role=args.role)
    except DisallowedTargetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    suite_path = DEFAULT_SUITES_DIR / f"{args.suite}.yaml"
    suite = runner.load_suite(suite_path)

    version_info = target.version()
    target_build_sha = version_info["build_sha"]

    run_id = args.run_id or f"run_{uuid.uuid4().hex[:12]}"
    print(f"atlas-redteam run {run_id} — suite={args.suite} target={args.target}")

    findings = runner.run_suite(target, suite, target_build_sha, run_id=run_id)

    store = FindingsStore(Path(args.db) if args.db else DEFAULT_DB_PATH)
    store.insert_many(findings)
    store.close()

    coverage = build_coverage_matrix(runner.probe_taxonomy_map(suite))
    DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = DEFAULT_REPORTS_DIR / f"{run_id}.html"
    report_path.write_text(render_report(run_id, target_build_sha, findings, coverage))
    print(f"report: {report_path.relative_to(REPO_ROOT)}")

    baseline = load_baseline(args.baseline or DEFAULT_BASELINE_PATH)
    result = check_regression(findings, baseline)

    print(f"findings: {len(findings)} total")
    print(f"  new: {len(result.new_findings)}")
    print(f"  ok (within baseline): {len(result.ok)}")
    print(f"  flaky: {len(result.flaky)}")
    print(f"  REGRESSIONS: {len(result.regressions)}")
    for f in result.regressions:
        print(
            f"    - {f.finding_id} [{f.taxonomy[0].id if f.taxonomy else '?'}] "
            f"asr={f.asr:.3f} ({f.asr_ci_low:.3f}-{f.asr_ci_high:.3f})"
        )

    target.close()
    return 1 if result.has_regression else 0


def cmd_baseline(args: argparse.Namespace) -> int:
    store = FindingsStore(Path(args.db) if args.db else DEFAULT_DB_PATH)
    findings = store.by_run(args.run_id)
    store.close()

    if not findings:
        print(f"error: no findings for run_id {args.run_id!r}", file=sys.stderr)
        return 2

    baseline = baseline_from_findings(findings)
    save_baseline(args.baseline or DEFAULT_BASELINE_PATH, baseline)
    print(f"baseline updated with {len(baseline)} mitigated finding(s) from run {args.run_id}")
    return 0


def cmd_check_regression(args: argparse.Namespace) -> int:
    store = FindingsStore(Path(args.db) if args.db else DEFAULT_DB_PATH)
    findings = store.by_run(args.run_id)
    store.close()

    baseline = load_baseline(args.baseline or DEFAULT_BASELINE_PATH)
    result = check_regression(findings, baseline)

    print(
        f"regressions: {len(result.regressions)}, new: {len(result.new_findings)}, "
        f"flaky: {len(result.flaky)}, ok: {len(result.ok)}"
    )
    return 1 if result.has_regression else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas-redteam")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a suite against Atlas")
    p_run.add_argument("--suite", required=True, help="suite name (suites/<name>.yaml)")
    p_run.add_argument("--target", default="http://127.0.0.1:8000")
    p_run.add_argument("--role", default="broker")
    p_run.add_argument("--run-id", default=None)
    p_run.add_argument("--db", default=None)
    p_run.add_argument("--baseline", default=None)
    p_run.set_defaults(func=cmd_run)

    p_baseline = sub.add_parser("baseline", help="promote a run's mitigated findings to baseline")
    p_baseline.add_argument("--run-id", required=True)
    p_baseline.add_argument("--db", default=None)
    p_baseline.add_argument("--baseline", default=None)
    p_baseline.set_defaults(func=cmd_baseline)

    p_check = sub.add_parser("check-regression", help="check a stored run against the baseline")
    p_check.add_argument("--run-id", required=True)
    p_check.add_argument("--db", default=None)
    p_check.add_argument("--baseline", default=None)
    p_check.set_defaults(func=cmd_check_regression)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
