# Threat model — Atlas

[`WEAKNESSES.md`](packages/atlas/WEAKNESSES.md) is a list of specific
vulnerabilities. This is the model they sit inside: what is worth
protecting, who might attack it, where the trust boundaries are, and
which control stands at each one.

Everything here describes the lab system. Atlas is intentionally
vulnerable and must never be deployed anywhere reachable — see
[`SECURITY.md`](SECURITY.md).

## System in one paragraph

Atlas is an internal AI assistant for a fictional insurer, Meridian
Mutual. Three surfaces: `/chat` (plain LLM), `/rag/query` (retrieval over
a pgvector corpus), and `/agent/act` (tool-calling agent). Callers assert
a role via an `X-Atlas-Role` header — `broker`, `adjuster`, or `hr`. Every
tool invocation goes through `atlas-control`, a separate policy service.
Telemetry flows to an OTel Collector and into ClickHouse.

## Assets

| Asset | Why it matters | Where it lives |
|---|---|---|
| HR document corpus | Cross-role disclosure to a broker is a contractual and regulatory breach | pgvector corpus, `hr` role only |
| Claims + customer data | Synthetic PII (SSN, DOB) standing in for regulated data | pgvector corpus, Postgres |
| Refund capability | Direct, quantifiable financial loss per misuse | `issue_refund` via `atlas-control` |
| Three canary tokens | Their appearance anywhere downstream is unambiguous proof of exfiltration | system prompt, RAG corpus, MCP docstore |
| System prompt | Contains internal handling instructions and a canary | `atlas.prompts` |
| Agent memory | Cross-session bleed is a privacy breach | Postgres, session-scoped |
| MCP tool descriptions | A changed description silently redirects agent behavior | `atlas-docstore`, `atlas-ticketing` |
| Decision + trace logs | The evidence base itself; also a second copy of sensitive content if careless | Postgres, ClickHouse |

## Actors

**Authorized but curious** — a real `broker` who asks for HR content.
Holds a valid role. The primary modeled adversary, because it needs no
compromise at all.

**Anonymous caller** — reaches `/chat` with no role. Bounded by having no
tool or retrieval access, but can still attempt prompt extraction.

**Malicious document author** — controls text that lands in the RAG
corpus or the MCP docstore. Never talks to Atlas directly; attacks
through content the model later reads. This is the indirect-injection
path.

**Compromised MCP server** — a supply-chain actor that serves altered
tool descriptions to steer the planner.

**Compromised model output** — the LLM itself as an untrusted component:
whatever the reason, it emits a tool call or text it shouldn't.

Explicitly out of scope: a host-level attacker with Docker socket or
database access. At that point the controls modeled here are moot.

## Trust boundaries

```
                    ┌─ untrusted ─┐
   caller (role header, unverified)
        │
        ▼  [B1]
   ┌──────────┐   [B2]   ┌───────────────┐
   │ atlas-api├─────────►│ atlas-control │  policy decisions, capability tokens
   └────┬─────┘          └───────┬───────┘
        │ [B3]                   │ [B5]
        ▼                        ▼
   pgvector corpus         MCP servers (docstore, ticketing)
        │ [B4]
        ▼
   Ollama (host)  ── [B6] ──►  Collector ──► ClickHouse
```

**B1 — caller → Atlas.** The role header is asserted, not authenticated.
This is a deliberate, documented simplification: there is no identity
provider in this lab, so every downstream control assumes the role is
*correctly attributed but not trustworthy as an authorization decision on
its own*. Real deployments must authenticate this boundary.

**B2 — Atlas → atlas-control.** The strongest boundary in the system.
Atlas cannot execute a tool itself; it can only ask. `atlas-control`
re-derives every decision from policy rather than trusting anything Atlas
sends. Crossing it requires a capability token that is single-use,
argument-scoped, and 30s-TTL.

**B3 — Atlas → retrieval corpus.** Enforced per-role before results reach
the prompt. Retrieved chunks are wrapped in untrusted-content markers —
defense in depth, explicitly *not* a security boundary, because the model
may ignore them.

**B4 — Atlas → Ollama.** Model output is untrusted input to everything
downstream. Nothing the model emits is executed directly; it can only
propose a step in a frozen plan.

**B5 — Atlas → MCP servers.** Tool descriptions are hash-pinned on first
sight; drift excludes the tool from the planner rather than warning.

**B6 — services → telemetry.** Prompt and completion content is carried
in span *events*, never attributes, and the Collector flags-then-redacts
canaries and PII before export — so the trace store doesn't become a
second copy of everything sensitive.

Network topology enforces part of this: `atlas_internal` is
`internal: true`, so Postgres, both MCP servers and `atlas-control` have
no route out of the host at all.

## Boundary → control → residual risk

Control IDs match
[`atlas-assurance`'s registry](packages/atlas-assurance/src/atlas_assurance/registry.py),
where each is linked to the test that exercises it.

| Boundary | Threat | Control | Residual risk |
|---|---|---|---|
| B1 | Caller asserts a role they shouldn't have | *(none — no authn in this lab)* | **Accepted, by design.** Documented here rather than implied |
| B3 | Broker reads HR documents | `retrieval-authorization` | Measured 1.000 → 0.000 ASR (N=20) |
| B3 | PII reaches the vector index | `pii-redaction-pre-embed` | SSN/DOB only; other PII shapes uncovered |
| B3 | Corpus tampered between ingest and retrieval | `corpus-integrity-hash-verification` | Detects, does not prevent |
| B3/B4 | Indirect injection via retrieved text | `untrusted-context-trust-boundary` | Defense in depth only; **LLM01 unchanged at 0.500 ASR** |
| B2 | Refund above the $500 cap | `tool-authorization-refund-threshold` | Measured 0.600 → 0.000 ASR (N=20) |
| B2 | Stolen or replayed tool credential | `capability-tokens` | Single-use, arg-scoped, 30s TTL |
| B2/B4 | Model executes a step outside the approved plan | `frozen-plan-execution` | Structurally unreachable via the API |
| B2 | Unbounded tool calls / split refunds | `session-budget-cap` | Call count + cumulative cents; **no token-spend budget** |
| B2 | Wrongly approved side effect | `staged-commit-rollback-window` | Bounded void window, needs a human to use it |
| B5 | Poisoned MCP tool description | `mcp-tool-description-hash-pinning` | Fails closed on drift |
| Memory | Cross-session data bleed | `session-scoped-memory` | Measured 0.200 → 0.000 ASR (N=20) |
| Detection | A control fails silently | `detection-tool-denial-visibility`, `detection-plan-deviation` | Real, but corpus-measured efficacy rests on one true positive |

## What this model does not cover

- **Authentication at B1.** The largest deliberate gap.
- **Generic jailbreak resistance.** No control targets it; `garak` DAN
  remains at 0.500 ASR, unchanged before and after.
- **Terminal output handling (LLM10).** Detection exists, enforcement
  does not — `cli.py` still prints model output unsanitized.
- **Eleven of twenty OWASP LLM/ASI categories** have no detector mapped;
  eight have no control. Both lists are enumerated rather than summarized
  in the coverage matrix and the control register.
- **Host compromise, model weights, training-time attacks.** Atlas
  consumes a pre-trained model it does not fine-tune.
