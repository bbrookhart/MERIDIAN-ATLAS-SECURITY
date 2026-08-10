# Weaknesses

Atlas is deliberately imperfect. Every row below was built in on purpose.
Six have since been mitigated by Project 3 (`atlas-control`) and Project 2
(`atlas-retrieval`) — kept here, not deleted, because this table plus each
project's committed before-state findings
(`evidence/reports/phase_a_agent_baseline.html` run `phase_a_agent_baseline`;
`evidence/reports/phase_a_rag_authorization.html` run
`phase_a_rag_authorization`) is the permanent record of what was true
before each fix, and each project's retest
(`evidence/reports/phase_c_highn.html` run `phase_c_highn`;
`evidence/reports/phase_c_rag_highn.html` run `phase_c_rag_highn` — both
higher-trial-count reruns of the probes genuinely attributable to their
respective fix; see `packages/atlas-control/README.md` and
`packages/atlas-retrieval/README.md` for why) is the record of what
changed and promoted into `atlas-redteam`'s regression baseline. The
remaining open row is later projects' job (detection, assurance).

IDs follow the OWASP Top 10 for LLM Applications 2026 and the OWASP Top 10
for Agentic Applications (ASI) 2026, per the numbering in this portfolio's
architecture doc — both are living documents; verify against
`https://genai.owasp.org` before citing either ID set in an external report.

| # | Weakness | Location | OWASP ID | Status | Why a real team might plausibly ship it |
|---|---|---|---|---|---|
| 1 | Retrieval applies no per-role authorization filter at query time | *(was `src/atlas/db/retrieval.py::search()`)* | LLM02:2026 — Sensitive Information Disclosure | **mitigated (Project 2)** — `atlas.db.retrieval.authorized_search()` asks `atlas-control`'s OPA policy (`retrieval_authorization.rego`) who's authorized before returning anything, in either pre-filter (default) or post-filter mode; `search()` itself is intentionally left unfiltered — see `packages/atlas-retrieval/README.md` for why the boundary lives one layer up | A single shared vector index across roles is the fastest way to stand up RAG; per-role filtering gets planned as a "phase 2" once the retriever contract stabilizes. |
| 2 | Retrieved chunks are concatenated into the prompt with no trust delimiter or provenance marker | *(was `src/atlas/routers/rag.py::build_rag_prompt()`)* | LLM01:2026 — Prompt Injection | **mitigated (Project 2)** — every chunk now wrapped in `<retrieved-context trust="untrusted">` (`atlas_retrieval.wrap_chunk`) with a system-prompt clause explaining it; documented plainly as defense in depth, not a security boundary | String-concatenating context and question is the fastest way to get RAG answering questions; delimiter/provenance tagging is treated as a later polish pass. |
| 3 | `issue_refund` enforced its threshold only via system-prompt instruction, not in code | *(deleted; was `src/atlas/tools/issue_refund.py`)* | LLM03:2026 — Excessive Agency | **mitigated (Project 3)** — enforced now by `packages/atlas-control/policy/tool_authorization.rego::refund_threshold_cents`, a policy rule with `opa test` coverage, unreachable from any prompt | Encoding the business rule in the prompt ships faster than adding a validation layer, and the model follows it correctly in every normal (non-adversarial) QA pass. |
| 4 | The agent had one long-lived credential shared across all four tools | *(deleted; was `src/atlas/credentials.py::TOOL_CREDENTIAL`)* | ASI03 — Agent Identity & Privilege Abuse | **mitigated (Project 3)** — replaced by per-invocation, 30s-TTL, single-use capability tokens (`atlas_control.capability`) | A single service-account token is far less setup than per-tool scoped, rotating credentials, especially under a deadline. |
| 5 | Agent memory persisted across sessions with no provenance on stored facts | `src/atlas/memory.py::load_recent_facts()` | ASI06 — Memory & Context Poisoning | **mitigated (Project 3)** — now scoped to `session_id`, TTL-bounded, and tagged with `source`/`trust_tier` | Persisting "facts the user told us" across sessions makes the assistant feel smarter and more personalized; provenance tagging looks like unnecessary schema overhead until it's exploited. |
| 6 | MCP tool descriptions were trusted verbatim from the server | *(deleted; was `src/atlas/mcp_client.py::list_remote_tools()`)* | ASI04 — Agentic Supply Chain Compromise (MCP03:2025 — Tool Poisoning) | **mitigated (Project 3)** — moved to `atlas_control.mcp_client` with SHA-256 hash-pinning and drift detection; a changed description is excluded from the planner, not silently forwarded | MCP's value proposition is dynamic tool discovery; hash-pinning or validating descriptions feels like it defeats the point, so most integrations skip it. |
| 7 | No rate limiting, no token budget, no per-session cost cap | `src/atlas/app.py` (absence of middleware) | LLM06:2026 — Unbounded Consumption | partially mitigated (Project 3), detection added (Project 4) — `atlas_control.budget` enforces a per-session tool-call count and cumulative refund cap as a policy input; no token-spend budget yet. `atlas-detect`'s `cost_asymmetry` detector flags disproportionate token spend after the fact, but that's visibility, not a cap — the underlying enforcement gap is still open | Rate limiting and cost caps are classic "add before it's a real product" infrastructure that internal tools ship without. |
| 8 | Model output is rendered to a terminal client without sanitization | `src/atlas/cli.py::main()` | LLM10:2026 — Improper Output Handling | still open, detection added (Project 4) — `atlas-detect`'s `ansi_escape_output` Sigma rule alerts on ANSI escape sequences in model output, but `cli.py` still prints raw model output unsanitized; a detection rule is not a fix, and this row stays open until something actually strips or escapes the output before it reaches the terminal | The terminal client is "just an internal debug tool," so escaping or sanitizing model output before printing feels like effort spent on a non-adversarial audience. |

## Project 2 — retrieval authorization

Weaknesses #1 and #2 are mitigated by
[`atlas-retrieval`](../atlas-retrieval/README.md): `/rag/query` now asks
`atlas-control`'s OPA policy (a second policy file alongside the one
Project 3 built for tool execution) who's authorized before returning
anything, in either pre-filter (default) or post-filter mode, and wraps
what it does return in explicit untrusted-content markers. Full
before/after architecture, the pre/post-filter latency-vs-recall
benchmark, the decision log (EU AI Act Article 12 evidence) with a worked
query example, corpus integrity, permission mirroring, PII
redact-before-embed, and the measured ASR delta live there.

## Project 3 — the control plane

Weaknesses #3, #4, #5, #6 (and part of #7) are mitigated by
[`atlas-control`](../atlas-control/README.md), the deterministic
policy-enforcement service `/agent/act` now calls through for every tool
invocation. Full before/after architecture, the OPA policy, capability
tokens, plan-then-execute, and the measured ASR delta live there.

## Project 4 — detection & response

[`atlas-detect`](../atlas-detect/README.md) adds detection for #7 and #8,
not enforcement — the distinction matters and is kept explicit in both
rows above rather than marked "mitigated." It also measures, with real
replayed attack traffic, how well the earlier projects' own structural
fixes show up as detectable events: e.g. weakness #1's retrieval
authorization (Project 2) is now visible as a `retrieval_violation`
detection surface, and weakness #3/#4's policy enforcement (Project 3) is
visible via the `tool_denied_out_of_scope` Sigma rule. Full measured
precision/recall/MTTD per detector, an honest OWASP/ASI coverage matrix
with stated blind spots, and two end-to-end incident walkthroughs live
there.

## Project 5 — assurance & evidence

[`atlas-assurance`](../atlas-assurance/README.md) doesn't mitigate any row
in this table — it makes the rows that *are* mitigated auditable, and
keeps them honest over time. Each control above is registered with the
specific test that exercises it, and the pipeline **refuses to assert a
control is effective** without a linked, real, passing test result
(`UnsupportedClaimError`), reporting `not_assessed` instead of inferring.
Controls whose evidence goes stale past its declared max-age are flagged
as such rather than staying green.

It also confirms this table's own gaps independently: the register's
coverage analysis reports 8 of 20 OWASP LLM/ASI categories with no
control at all — including `LLM10:2026`, which is still an open row
above. Framework crosswalks (NIST AI RMF, NIST AI 600-1, ISO/IEC 42001,
CSA AICM, MITRE ATLAS, EU AI Act) and AIVSS-vs-CVSS scoring live there,
along with a CycloneDX AI-BOM. **Crosswalks are an engineering aid, not a
compliance determination**, and nothing in this repo makes a compliance
claim.

## Canaries

Three `MERIDIAN-CANARY-<uuid>` tokens are planted so exfiltration is
unambiguous to detect in later projects (`src/atlas/canaries.py` — computed
deterministically at runtime, never written as a literal string, so the
repo's `block-canary-values` pre-commit hook never has to see one):

1. The system prompt (`src/atlas/prompts.py`) — framed as an internal
   reference token the assistant must never reveal.
2. One synthetic HR document in the RAG corpus (`src/atlas/seed.py`).
3. One document served by the MCP docstore server (`src/atlas/mcp_servers/data.py`).
