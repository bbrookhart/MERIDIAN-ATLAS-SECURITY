"""Framework crosswalk — an engineering aid, not a compliance determination.

A crosswalk tells you *where to look* in another framework for a related
control or obligation; it does not certify that Atlas (or anything else)
complies with that framework. ISO/IEC 42001 certifies a management
*system*; the EU AI Act regulates a *product*. Conflating the two is a
common error this README does not make.

Taxonomy IDs are the portfolio's own canonical set —
`atlas_redteam.coverage.LLM_CATEGORIES`/`ASI_CATEGORIES`, imported here
rather than redefined a third time (`atlas_detect.coverage` already
reuses the same source).

Per-framework sourcing, and what's verified vs. reconstructed:

- **EU AI Act** articles and current dates are copied verbatim from this
  portfolio's own master prompt (Regulation (EU) 2026/1744; Art. 9/10/11/
  12/13/14/15/17) — that document is this project's ground truth for the
  Act, no re-fetch needed.
- **NIST AI RMF** (Govern/Map/Measure/Manage) and **NIST AI 600-1**'s 12
  named GenAI risk categories are stable, previously-published documents
  (AI RMF 1.0, Jan 2023; AI 600-1, Jul 2024) cited from established
  knowledge, not re-verified live this session.
- **ISO/IEC 42001:2023** Annex A objective titles (A.2–A.10) were fetched
  live this session (isms.online, cross-checked against two other current
  sources) — mapped at the *objective* level only, not fabricated
  sub-control numbers.
- **CSA AI Controls Matrix (AICM) v1.1** (2026): only six domain names
  were confirmed live this session (Model Security/MDS is new in v1.1;
  Data Security and Privacy Lifecycle Management; Governance, Risk and
  Compliance; Application and Interface Security; Supply Chain
  Transparency; Identity and Access Management). The full 18-domain list
  lives in AICM's controls spreadsheet, which wasn't fetched — every
  mapping below uses only one of these six *verified* names, rather than
  guessing at unverified ones for a better-sounding fit.
- **MITRE ATLAS** tactic names (Reconnaissance through Impact, mirroring
  ATT&CK's structure) are cited by tactic name only, from established
  knowledge — specific AML.Txxxx technique IDs are not cited, since those
  weren't independently re-verified this session either.
"""

from __future__ import annotations

from atlas_redteam.coverage import ALL_CATEGORIES

from atlas_assurance.models import Framework, FrameworkRef

_NIST_RMF_FUNCTION: dict[str, str] = {
    "LLM01:2026": "Measure",
    "LLM02:2026": "Manage",
    "LLM03:2026": "Govern",
    "LLM04:2026": "Map",
    "LLM05:2026": "Measure",
    "LLM06:2026": "Manage",
    "LLM07:2026": "Measure",
    "LLM08:2026": "Measure",
    "LLM09:2026": "Map",
    "LLM10:2026": "Manage",
    "ASI01": "Manage",
    "ASI02": "Manage",
    "ASI03": "Govern",
    "ASI04": "Map",
    "ASI05": "Manage",
    "ASI06": "Measure",
    "ASI07": "Manage",
    "ASI08": "Measure",
    "ASI09": "Govern",
    "ASI10": "Govern",
}

_NIST_600_1_CATEGORY: dict[str, str] = {
    "LLM01:2026": "Information Security",
    "LLM02:2026": "Data Privacy",
    "LLM03:2026": "Human-AI Configuration",
    "LLM04:2026": "Value Chain and Component Integration",
    "LLM05:2026": "Information Integrity",
    "LLM06:2026": "Information Security",
    "LLM07:2026": "Confabulation",
    "LLM08:2026": "Data Privacy",
    "LLM09:2026": "Information Security",
    "LLM10:2026": "Information Integrity",
    "ASI01": "Human-AI Configuration",
    "ASI02": "Information Security",
    "ASI03": "Information Security",
    "ASI04": "Value Chain and Component Integration",
    "ASI05": "Information Security",
    "ASI06": "Information Integrity",
    "ASI07": "Information Security",
    "ASI08": "Human-AI Configuration",
    "ASI09": "Human-AI Configuration",
    "ASI10": "Human-AI Configuration",
}

_ISO_42001_OBJECTIVE: dict[str, str] = {
    "LLM01:2026": "A.9 Use of AI Systems",
    "LLM02:2026": "A.7 Data for AI Systems",
    "LLM03:2026": "A.9 Use of AI Systems",
    "LLM04:2026": "A.10 Third-Party and Customer Relationships",
    "LLM05:2026": "A.7 Data for AI Systems",
    "LLM06:2026": "A.4 Resources for AI Systems",
    "LLM07:2026": "A.5 Assessing Impacts of AI Systems",
    "LLM08:2026": "A.8 Information for Interested Parties of AI Systems",
    "LLM09:2026": "A.6 AI System Life Cycle",
    "LLM10:2026": "A.9 Use of AI Systems",
    "ASI01": "A.6 AI System Life Cycle",
    "ASI02": "A.9 Use of AI Systems",
    "ASI03": "A.9 Use of AI Systems",
    "ASI04": "A.10 Third-Party and Customer Relationships",
    "ASI05": "A.6 AI System Life Cycle",
    "ASI06": "A.7 Data for AI Systems",
    "ASI07": "A.6 AI System Life Cycle",
    "ASI08": "A.5 Assessing Impacts of AI Systems",
    "ASI09": "A.9 Use of AI Systems",
    "ASI10": "A.9 Use of AI Systems",
}

_CSA_AICM_DOMAIN: dict[str, str] = {
    "LLM01:2026": "Application and Interface Security",
    "LLM02:2026": "Data Security and Privacy Lifecycle Management",
    "LLM03:2026": "Governance, Risk and Compliance",
    "LLM04:2026": "Supply Chain Transparency",
    "LLM05:2026": "Model Security (MDS)",
    "LLM06:2026": "Application and Interface Security",
    "LLM07:2026": "Governance, Risk and Compliance",
    "LLM08:2026": "Data Security and Privacy Lifecycle Management",
    "LLM09:2026": "Data Security and Privacy Lifecycle Management",
    "LLM10:2026": "Application and Interface Security",
    "ASI01": "Governance, Risk and Compliance",
    "ASI02": "Application and Interface Security",
    "ASI03": "Identity and Access Management",
    "ASI04": "Supply Chain Transparency",
    "ASI05": "Model Security (MDS)",
    "ASI06": "Data Security and Privacy Lifecycle Management",
    "ASI07": "Application and Interface Security",
    "ASI08": "Application and Interface Security",
    "ASI09": "Governance, Risk and Compliance",
    "ASI10": "Governance, Risk and Compliance",
}

_MITRE_ATLAS_TACTIC: dict[str, str] = {
    "LLM01:2026": "Initial Access",
    "LLM02:2026": "Exfiltration",
    "LLM03:2026": "Impact",
    "LLM04:2026": "Resource Development",
    "LLM05:2026": "ML Attack Staging",
    "LLM06:2026": "Impact",
    "LLM07:2026": "Impact",
    "LLM08:2026": "Collection",
    "LLM09:2026": "ML Model Access",
    "LLM10:2026": "Impact",
    "ASI01": "Execution",
    "ASI02": "Execution",
    "ASI03": "Privilege Escalation",
    "ASI04": "Resource Development",
    "ASI05": "Execution",
    "ASI06": "Persistence",
    "ASI07": "Collection",
    "ASI08": "Impact",
    "ASI09": "Defense Evasion",
    "ASI10": "Persistence",
}

# Verbatim from the portfolio master prompt: Regulation (EU) 2026/1744;
# Annex III standalone high-risk from 2 Dec 2027, Annex I embedded from
# 2 Aug 2028, Art. 50 transparency from 2 Aug 2026.
_EU_AI_ACT_ARTICLE: dict[str, str] = {
    "LLM01:2026": "Art. 15 (accuracy, robustness, cybersecurity)",
    "LLM02:2026": "Art. 10 (data governance)",
    "LLM03:2026": "Art. 14 (human oversight)",
    "LLM04:2026": "Art. 17 (quality management system)",
    "LLM05:2026": "Art. 10 (data governance)",
    "LLM06:2026": "Art. 15 (accuracy, robustness, cybersecurity)",
    "LLM07:2026": "Art. 13 (transparency)",
    "LLM08:2026": "Art. 12 (record-keeping)",
    "LLM09:2026": "Art. 15 (accuracy, robustness, cybersecurity)",
    "LLM10:2026": "Art. 13 (transparency)",
    "ASI01": "Art. 14 (human oversight)",
    "ASI02": "Art. 9 (risk management)",
    "ASI03": "Art. 14 (human oversight)",
    "ASI04": "Art. 17 (quality management system)",
    "ASI05": "Art. 15 (accuracy, robustness, cybersecurity)",
    "ASI06": "Art. 10 (data governance)",
    "ASI07": "Art. 11 (technical documentation)",
    "ASI08": "Art. 9 (risk management)",
    "ASI09": "Art. 14 (human oversight)",
    "ASI10": "Art. 14 (human oversight)",
}


def crosswalk_for(taxonomy_id: str) -> list[FrameworkRef]:
    if taxonomy_id not in ALL_CATEGORIES:
        return []
    return [
        FrameworkRef(Framework.NIST_AI_RMF, _NIST_RMF_FUNCTION[taxonomy_id]),
        FrameworkRef(Framework.NIST_AI_600_1, _NIST_600_1_CATEGORY[taxonomy_id]),
        FrameworkRef(Framework.ISO_42001, _ISO_42001_OBJECTIVE[taxonomy_id]),
        FrameworkRef(Framework.CSA_AICM, _CSA_AICM_DOMAIN[taxonomy_id]),
        FrameworkRef(Framework.MITRE_ATLAS, _MITRE_ATLAS_TACTIC[taxonomy_id]),
        FrameworkRef(Framework.EU_AI_ACT, _EU_AI_ACT_ARTICLE[taxonomy_id]),
    ]


def full_crosswalk() -> dict[str, list[FrameworkRef]]:
    return {taxonomy_id: crosswalk_for(taxonomy_id) for taxonomy_id in ALL_CATEGORIES}
