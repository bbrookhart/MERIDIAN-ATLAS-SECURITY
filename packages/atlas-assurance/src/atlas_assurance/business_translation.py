"""For the top findings by AIVSS score: technical finding → what an
attacker achieves → business impact for an insurer → control → residual
risk → the evidence proving the control works. Written as structured
data (not prose) so `executive_summary.py` generates its own text from
this, rather than duplicating a second hand-written version.

The prose narrative fields (`attacker_achieves`, `business_impact_
insurer`) are looked up by probe family from a small, explicit,
hand-written table — the one piece of genuinely hand-authored prose in
the whole pipeline, same as `registry.py`'s control descriptions. Every
other field on `BusinessTranslation` is a real, traceable ID.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas_schema import Finding

from atlas_assurance.aivss import AivssResult
from atlas_assurance.models import ControlAssertion

_NARRATIVES: dict[str, tuple[str, str]] = {
    "garak:dan.Dan_11_0": (
        "Bypasses the system prompt's safety framing via a published jailbreak template.",
        (
            "A logged-in user extracts the assistant's hidden instructions or gets it to act "
            "outside its intended scope, in a system a claims customer or partner can reach — "
            "regulatory and reputational exposure even without a direct financial loss."
        ),
    ),
    "pyrit:canary-extraction-prefix-injection": (
        "Extracts an internal reference token from the model's response via prefix injection.",
        (
            "Proof that internal system context (which could be a real customer PII field or "
            "internal claims-handling instruction) can leak through the chat interface to any user."
        ),
    ),
    "pyrit:canary-extraction-prefix-injection-agent": (
        "Extracts an internal reference token from an agent-surface response via prefix injection.",
        (
            "Same exposure as the chat-surface variant, but through the tool-executing agent — a "
            "leak here sits closer to systems that can also take real actions (refunds, tickets)."
        ),
    ),
    "pyrit:canary-extraction-prefix-injection-rag": (
        "Extracts an internal reference token surfaced via retrieved document content.",
        (
            "Confirms retrieval-augmented answers can carry sensitive planted content into a "
            "response — the RAG-specific analogue of a direct prompt leak."
        ),
    ),
    "deepteam:excessive-agency": (
        "Probes whether the agent will take a tool action beyond its intended authority.",
        (
            "An agent that self-authorizes beyond its intended scope is an insurer's definition of "
            "an uncontrolled claims-processing system — the underwriting-relevant failure mode."
        ),
    ),
    "excessive-agency-probe:refund-threshold-bypass": (
        "Frames an over-threshold refund request to get `issue_refund` invoked above the $500 cap.",
        (
            "Direct dollar loss per successful bypass, multiplied across every session an attacker "
            "can reach — the single most insurable, quantifiable finding in this portfolio."
        ),
    ),
    "memory-probe:cross-session-memory-leak": (
        "Plants a fact in one session, asks a second, unrelated session to recall it.",
        (
            "Customer A's claim details surfacing in customer B's conversation — a direct privacy "
            "breach with statutory notification obligations in most jurisdictions."
        ),
    ),
    "retrieval-leak-probe:broker-hr-content-leak": (
        "A broker-role session asks directly for HR-only document content.",
        (
            "Cross-role disclosure of employee data to a business partner — a contractual and "
            "regulatory breach distinct from, and often worse than, a customer-facing leak."
        ),
    ),
}
_DEFAULT_NARRATIVE = (
    "An automated red-team probe against this finding's taxonomy category.",
    (
        "Impact not yet individually narrated for this probe family — see the linked finding's "
        "repro_command and evidence_path for the specific behavior observed."
    ),
)


@dataclass(frozen=True)
class BusinessTranslation:
    finding_id: str
    probe_id: str
    aivss_score: float
    technical_finding: str
    attacker_achieves: str
    business_impact_insurer: str
    control_ids: tuple[str, ...]
    control_names: tuple[str, ...]
    residual_risk: str
    evidence: dict[str, object]


def _resolve_assertions(
    finding: Finding,
    assertions_by_control_ref: dict[str, ControlAssertion],
    assertions_by_taxonomy: dict[str, list[ControlAssertion]],
) -> tuple[list[ControlAssertion], bool]:
    """Returns (assertions, matched_by_taxonomy_only).

    A finding's own `control_ref` is the direct link, but *before-state*
    findings (Project 1's `phase_a_*` runs, recorded before Projects 2/3
    existed) legitimately carry `control_ref=None` even though a control
    covering that exact taxonomy shipped later. Found live: without the
    taxonomy fallback, the phase_a broker-HR-leak finding reported "no
    control addresses this" while `retrieval-authorization` demonstrably
    does — a claim that would have been simply false in the executive
    summary.

    Every matching control is returned, not one. Also found live: the
    highest-scoring `garak:dan.Dan_11_0` finding is tagged both `ASI01`
    and `LLM01:2026`, and different controls address each — an earlier
    version returned whichever taxonomy ref happened to be listed first
    on the finding, which made the reported control an artifact of list
    order rather than a fact about coverage.
    """
    if finding.control_ref and finding.control_ref in assertions_by_control_ref:
        return [assertions_by_control_ref[finding.control_ref]], False

    matched: list[ControlAssertion] = []
    seen: set[str] = set()
    for ref in finding.taxonomy:
        for assertion in assertions_by_taxonomy.get(ref.id, []):
            if assertion.control.control_id not in seen:
                seen.add(assertion.control.control_id)
                matched.append(assertion)
    return matched, bool(matched)


def _residual_risk(
    finding: Finding, assertions: list[ControlAssertion], matched_by_taxonomy_only: bool
) -> str:
    if not assertions:
        return (
            "No control in the registry addresses this finding's taxonomy — residual risk is "
            "the full finding as observed."
        )
    failing = [a for a in assertions if not a.test_result.passed]
    if failing:
        names = ", ".join(a.control.control_id for a in failing)
        return f"Control(s) meant to address this are currently failing their own tests ({names}) — treat as unmitigated."
    if matched_by_taxonomy_only:
        # Deliberately does NOT say "before-state": found live that a
        # taxonomy match covers two genuinely different cases, and
        # conflating them misdescribes the second. `garak:dan.Dan_11_0`
        # is still open in the phase_c *retest* run at ASR 0.500 and
        # Project 1 never attributed it to any control — calling that a
        # "before-state finding fixed later" would be false.
        return (
            f"Not attributed to any control by Project 1 (run {finding.run_id}, status "
            f"{finding.status.value}, ASR {finding.asr:.3f}). The control(s) listed address this "
            f"finding's taxonomy category and are currently passing, but were not measured as "
            f"mitigating this specific probe — treat the observed rate as the residual."
        )
    return (
        f"Bounded by the measured post-control ASR upper bound "
        f"({finding.asr_ci_high:.3f}) for this finding's probe family, not zero."
    )


def top_business_translations(
    findings: list[Finding],
    aivss_results: list[AivssResult],
    assertions_by_control_ref: dict[str, ControlAssertion],
    n: int = 5,
    assertions_by_taxonomy: dict[str, list[ControlAssertion]] | None = None,
) -> list[BusinessTranslation]:
    assertions_by_taxonomy = assertions_by_taxonomy or {}
    findings_by_id = {f.finding_id: f for f in findings}

    # One row per probe, keeping its highest-scoring instance. The same
    # probe legitimately appears once per run (phase_a before-state,
    # phase_c retest, ...) — listing "top 5 risks" as three copies of one
    # probe would crowd out three genuinely distinct risks, which is less
    # informative, not more honest. Ties break toward the more recent run,
    # so the row shown reflects current state rather than DB row order.
    best_by_probe: dict[str, AivssResult] = {}
    for result in aivss_results:
        finding = findings_by_id[result.finding_id]
        current = best_by_probe.get(finding.probe_id)
        if current is None:
            best_by_probe[finding.probe_id] = result
            continue
        current_finding = findings_by_id[current.finding_id]
        if (result.aivss_score, finding.timestamp) > (
            current.aivss_score,
            current_finding.timestamp,
        ):
            best_by_probe[finding.probe_id] = result
    ranked = sorted(best_by_probe.values(), key=lambda r: r.aivss_score, reverse=True)[:n]

    translations = []
    for result in ranked:
        finding = findings_by_id[result.finding_id]
        attacker_achieves, business_impact = _NARRATIVES.get(finding.probe_id, _DEFAULT_NARRATIVE)
        assertions, matched_by_taxonomy_only = _resolve_assertions(
            finding, assertions_by_control_ref, assertions_by_taxonomy
        )
        translations.append(
            BusinessTranslation(
                finding_id=finding.finding_id,
                probe_id=finding.probe_id,
                aivss_score=result.aivss_score,
                technical_finding=f"{finding.probe_id} ({finding.tool}) — {finding.status.value}",
                attacker_achieves=attacker_achieves,
                business_impact_insurer=business_impact,
                control_ids=tuple(a.control.control_id for a in assertions),
                control_names=tuple(a.control.name for a in assertions),
                residual_risk=_residual_risk(finding, assertions, matched_by_taxonomy_only),
                evidence={
                    "finding_id": finding.finding_id,
                    "run_id": finding.run_id,
                    "control_ids": [a.control.control_id for a in assertions],
                    "test_refs": [a.control.test_ref for a in assertions],
                },
            )
        )
    return translations


__all__ = ["BusinessTranslation", "top_business_translations"]
