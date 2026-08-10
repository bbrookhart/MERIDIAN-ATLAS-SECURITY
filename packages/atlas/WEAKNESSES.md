# Weaknesses

Atlas is deliberately imperfect. Every row below was built in on purpose.
Four have since been mitigated by Project 3 (`atlas-control`) — kept here,
not deleted, because this table plus Project 1's committed before-state
findings (`evidence/reports/phase_a_agent_baseline.html`,
run `phase_a_agent_baseline`) is the permanent record of what was true
before the fix, and Project 3's own retest (`run phase_c_agent_baseline`)
is the record of what changed. The remaining open rows are later projects'
job (retrieval authorization, detection, assurance).

IDs follow the OWASP Top 10 for LLM Applications 2026 and the OWASP Top 10
for Agentic Applications (ASI) 2026, per the numbering in this portfolio's
architecture doc — both are living documents; verify against
`https://genai.owasp.org` before citing either ID set in an external report.

| # | Weakness | Location | OWASP ID | Status | Why a real team might plausibly ship it |
|---|---|---|---|---|---|
| 1 | Retrieval applies no per-role authorization filter at query time | `src/atlas/db/retrieval.py::search()` | LLM02:2026 — Sensitive Information Disclosure | open (Project 2) | A single shared vector index across roles is the fastest way to stand up RAG; per-role filtering gets planned as a "phase 2" once the retriever contract stabilizes. |
| 2 | Retrieved chunks are concatenated into the prompt with no trust delimiter or provenance marker | `src/atlas/routers/rag.py::build_rag_prompt()` | LLM01:2026 — Prompt Injection | open (Project 2) | String-concatenating context and question is the fastest way to get RAG answering questions; delimiter/provenance tagging is treated as a later polish pass. |
| 3 | `issue_refund` enforced its threshold only via system-prompt instruction, not in code | *(deleted; was `src/atlas/tools/issue_refund.py`)* | LLM03:2026 — Excessive Agency | **mitigated (Project 3)** — enforced now by `packages/atlas-control/policy/tool_authorization.rego::refund_threshold_cents`, a policy rule with `opa test` coverage, unreachable from any prompt | Encoding the business rule in the prompt ships faster than adding a validation layer, and the model follows it correctly in every normal (non-adversarial) QA pass. |
| 4 | The agent had one long-lived credential shared across all four tools | *(deleted; was `src/atlas/credentials.py::TOOL_CREDENTIAL`)* | ASI03 — Agent Identity & Privilege Abuse | **mitigated (Project 3)** — replaced by per-invocation, 30s-TTL, single-use capability tokens (`atlas_control.capability`) | A single service-account token is far less setup than per-tool scoped, rotating credentials, especially under a deadline. |
| 5 | Agent memory persisted across sessions with no provenance on stored facts | `src/atlas/memory.py::load_recent_facts()` | ASI06 — Memory & Context Poisoning | **mitigated (Project 3)** — now scoped to `session_id`, TTL-bounded, and tagged with `source`/`trust_tier` | Persisting "facts the user told us" across sessions makes the assistant feel smarter and more personalized; provenance tagging looks like unnecessary schema overhead until it's exploited. |
| 6 | MCP tool descriptions were trusted verbatim from the server | *(deleted; was `src/atlas/mcp_client.py::list_remote_tools()`)* | ASI04 — Agentic Supply Chain Compromise (MCP03:2025 — Tool Poisoning) | **mitigated (Project 3)** — moved to `atlas_control.mcp_client` with SHA-256 hash-pinning and drift detection; a changed description is excluded from the planner, not silently forwarded | MCP's value proposition is dynamic tool discovery; hash-pinning or validating descriptions feels like it defeats the point, so most integrations skip it. |
| 7 | No rate limiting, no token budget, no per-session cost cap | `src/atlas/app.py` (absence of middleware) | LLM06:2026 — Unbounded Consumption | partially mitigated (Project 3) — `atlas_control.budget` enforces a per-session tool-call count and cumulative refund cap as a policy input; no token-spend budget yet | Rate limiting and cost caps are classic "add before it's a real product" infrastructure that internal tools ship without. |
| 8 | Model output is rendered to a terminal client without sanitization | `src/atlas/cli.py::main()` | LLM10:2026 — Improper Output Handling | open (Project 4/5) | The terminal client is "just an internal debug tool," so escaping or sanitizing model output before printing feels like effort spent on a non-adversarial audience. |

## Project 3 — the control plane

Weaknesses #3, #4, #5, #6 (and part of #7) are mitigated by
[`atlas-control`](../atlas-control/README.md), the deterministic
policy-enforcement service `/agent/act` now calls through for every tool
invocation. Full before/after architecture, the OPA policy, capability
tokens, plan-then-execute, and the measured ASR delta live there.

## Canaries

Three `MERIDIAN-CANARY-<uuid>` tokens are planted so exfiltration is
unambiguous to detect in later projects (`src/atlas/canaries.py` — computed
deterministically at runtime, never written as a literal string, so the
repo's `block-canary-values` pre-commit hook never has to see one):

1. The system prompt (`src/atlas/prompts.py`) — framed as an internal
   reference token the assistant must never reveal.
2. One synthetic HR document in the RAG corpus (`src/atlas/seed.py`).
3. One document served by the MCP docstore server (`src/atlas/mcp_servers/data.py`).
