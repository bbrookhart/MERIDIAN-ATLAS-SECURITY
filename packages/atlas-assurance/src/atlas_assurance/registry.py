"""The one hand-authored input to the whole pipeline.

Every field here is a claim about *what exists* (which control, which
test proves it, which framework clauses it maps to) — never a claim
about whether it's *currently passing*. Pass/fail, timestamps, and
freshness are computed later from real ingested `TestResult`s
(`evidence_store.py`); nothing here is itself evidence.

`control_ref` values for the first three controls are copied verbatim
from `Finding.control_ref` on the real `mitigated` findings already
committed in `evidence/findings.duckdb` (checked live via `atlas_redteam.
store.FindingsStore`), so they're traceable back to Project 1's own
before/after record, not re-described from scratch.

`test_ref` format mirrors `ingest.junit`/`ingest.opa`'s `TestResult.
test_id` exactly: `"<package>::<classname>::<name>"` for pytest,
`"opa::<rego package>::<name>"` for `opa test`.
"""

from __future__ import annotations

from atlas_assurance.models import ControlDef, Framework, FrameworkRef

CONTROLS: tuple[ControlDef, ...] = (
    ControlDef(
        control_id="tool-authorization-refund-threshold",
        name="Refund threshold enforced in policy, not just prompt instruction",
        description=(
            "issue_refund's $500 cap is a Rego rule evaluated server-side for every "
            "tool call, unreachable from any prompt (WEAKNESSES.md #3)."
        ),
        control_ref="packages/atlas-control/policy/tool_authorization.rego::refund_threshold_cents",
        test_ref="opa::data.atlas.authz_test::test_refund_over_threshold_is_denied_regardless_of_framing",
        max_age_days=30,
        addresses_taxonomy=("LLM03:2026", "ASI02"),
    ),
    ControlDef(
        control_id="session-scoped-memory",
        name="Agent memory scoped to one session, provenance-tagged",
        description=(
            "Facts persisted to memory carry source/trust_tier and a session-scoped "
            "TTL-bounded query, closing WEAKNESSES.md #5's cross-session leak."
        ),
        control_ref=(
            "packages/atlas/src/atlas/memory.py::load_recent_facts (session-scoped, Project 3)"
        ),
        test_ref="atlas::tests.test_memory_provenance::test_load_recent_facts_scopes_query_to_one_session",
        max_age_days=30,
        addresses_taxonomy=("ASI06",),
    ),
    ControlDef(
        control_id="retrieval-authorization",
        name="Retrieval authorized per-role before chunks reach the prompt",
        description=(
            "OPA-backed role visibility, pre-filter by default, closing "
            "WEAKNESSES.md #1's unfiltered cross-role retrieval."
        ),
        control_ref=(
            "atlas_control.retrieval_policy.authorize_retrieval "
            "(policy/retrieval_authorization.rego, role_visibility) + "
            "atlas.db.retrieval.authorized_search (pre-filter enforcement)"
        ),
        test_ref="opa::data.atlas.retrieval_authz_test::test_hr_content_is_denied_to_broker_regardless_of_chunk_count",
        max_age_days=30,
        addresses_taxonomy=("LLM02:2026",),
    ),
    ControlDef(
        control_id="capability-tokens",
        name="Per-invocation, single-use, scoped capability tokens",
        description=(
            "Replaces the one long-lived shared tool credential (WEAKNESSES.md #4) "
            "with 30s-TTL, argument-scoped, single-use tokens."
        ),
        control_ref="packages/atlas-control/src/atlas_control/capability.py::mint/redeem",
        test_ref="atlas-control::tests.test_capability::test_redeem_rejects_replay",
        max_age_days=30,
        addresses_taxonomy=("ASI03",),
    ),
    ControlDef(
        control_id="frozen-plan-execution",
        name="Plan frozen and hashed before execution; steps outside it are rejected",
        description=(
            "execute_step(plan_id, index) is the only execution entrypoint — an "
            "index outside the approved, frozen plan is structurally unreachable."
        ),
        control_ref="packages/atlas-control/src/atlas_control/plan.py::execute_step",
        test_ref="atlas-control::tests.test_plan::test_execute_step_rejects_out_of_range_index",
        max_age_days=30,
        addresses_taxonomy=("ASI01",),
    ),
    ControlDef(
        control_id="session-budget-cap",
        name="Per-session tool-call count and cumulative refund cap",
        description="Blocks unbounded tool-call volume and split-refund threshold evasion.",
        control_ref="packages/atlas-control/src/atlas_control/budget.py::record_tool_call",
        test_ref="atlas-control::tests.test_policy::test_session_budget_exhausted",
        max_age_days=30,
        addresses_taxonomy=("LLM06:2026", "ASI08"),
    ),
    ControlDef(
        control_id="mcp-tool-description-hash-pinning",
        name="MCP tool descriptions hash-pinned; drift excludes the tool from the planner",
        description=(
            "Closes WEAKNESSES.md #6 (MCP03:2025 tool poisoning) — a changed "
            "description is a security event, not new information for the planner."
        ),
        control_ref="packages/atlas-control/src/atlas_control/mcp_client.py::_check_and_pin",
        test_ref="atlas-control::tests.test_mcp_client::test_changed_description_is_drift_and_excluded",
        max_age_days=30,
        addresses_taxonomy=("ASI04", "LLM04:2026"),
    ),
    ControlDef(
        control_id="staged-commit-rollback-window",
        name="Refund/email actions staged with a bounded void window before finalizing",
        description="Gives a human a real window to void a wrongly-approved side-effecting action.",
        control_ref="packages/atlas-control/src/atlas_control/staged_commit.py::stage/void",
        test_ref="atlas-control::tests.test_staged_commit::test_void_within_window_succeeds",
        max_age_days=30,
        addresses_taxonomy=("ASI02",),
    ),
    ControlDef(
        control_id="pii-redaction-pre-embed",
        name="SSN/DOB redacted before embedding",
        description="Sensitive fields never enter the vector index in the first place.",
        control_ref="packages/atlas-retrieval/src/atlas_retrieval/pii.py::redact_pii",
        test_ref="atlas-retrieval::tests.test_pii::test_redact_pii_strips_ssn",
        max_age_days=30,
        addresses_taxonomy=("LLM02:2026",),
    ),
    ControlDef(
        control_id="corpus-integrity-hash-verification",
        name="Retrieved chunk content-hash verified against ingestion-time hash",
        description="Detects out-of-band corpus tampering between ingest and retrieval.",
        control_ref=(
            "packages/atlas-retrieval/src/atlas_retrieval/corpus_integrity.py::verify_content_hash"
        ),
        test_ref="atlas-retrieval::tests.test_corpus_integrity::test_verify_content_hash_fails_on_out_of_band_tamper",
        max_age_days=30,
        addresses_taxonomy=("LLM05:2026",),
    ),
    ControlDef(
        control_id="untrusted-context-trust-boundary",
        name="Retrieved chunks wrapped with an explicit untrusted-content marker",
        description="Defense in depth against indirect injection via retrieved documents.",
        control_ref="packages/atlas-retrieval/src/atlas_retrieval/trust_boundary.py::wrap_chunk",
        test_ref="atlas-retrieval::tests.test_trust_boundary::test_wrap_chunk_includes_provenance_and_trust_tier",
        max_age_days=30,
        addresses_taxonomy=("LLM01:2026",),
    ),
    ControlDef(
        control_id="detection-tool-denial-visibility",
        name="Denied tool invocations are a detectable trace-store event",
        description=(
            "Measured in Project 4 (phase3_results.json): precision 1.0 on genuine "
            "over-threshold attempts, recall limited by model execution fidelity, "
            "not detector blindness — see packages/atlas-detect/README.md."
        ),
        control_ref="packages/atlas-detect/sigma/tool_denied_out_of_scope.yml",
        test_ref="atlas-detect::tests.test_sigma_rules::test_tool_denied_rule_matches_only_denied_policy_decisions",
        max_age_days=30,
        addresses_taxonomy=("LLM03:2026", "ASI03"),
    ),
    ControlDef(
        control_id="detection-plan-deviation",
        name="An execute_step call outside the frozen plan is a detectable event",
        description=(
            "Measured live in Project 4's goal-hijack incident walkthrough: 4.7s "
            "detection latency on a real out-of-range execute_step call."
        ),
        control_ref="packages/atlas-detect/src/atlas_detect/detectors/plan_deviation.py::detect",
        test_ref="atlas-detect::tests.test_detectors::test_plan_deviation_detects_a_real_deviation",
        max_age_days=30,
        addresses_taxonomy=("ASI01",),
    ),
)


def crosswalk_refs_for_control(control: ControlDef) -> list[FrameworkRef]:
    """Deferred to crosswalk.py (Phase 3) — each control's taxonomy IDs are
    looked up there so this module stays a pure, static registry.
    """
    from atlas_assurance.crosswalk import crosswalk_for

    refs: list[FrameworkRef] = []
    for taxonomy_id in control.addresses_taxonomy:
        refs.extend(crosswalk_for(taxonomy_id))
    return refs


__all__ = ["CONTROLS", "Framework", "FrameworkRef", "crosswalk_refs_for_control"]
