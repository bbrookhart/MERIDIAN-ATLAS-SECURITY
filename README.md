# meridian-atlas-security

<!-- Once published, add the CI badge (replace OWNER/REPO):
[![ci](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml) -->
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)

Five surfaces of one AI system, attacked, controlled, retested and mapped
to evidence.

Atlas is a deliberately vulnerable LLM claims-handling assistant for a
fictional insurer. Everything else in this repo attacks it, controls it,
measures whether the control held, watches for the control failing
silently, and turns all of that into audit evidence.

## The evidence

Attack success rate before and after each control, from
[`evidence/findings.duckdb`](evidence/findings.duckdb). Intervals are
Wilson 95% CIs; `N` is trial count. Every row links to a committed run.

| OWASP 2026 | Attack | Pre-control ASR | Post-control ASR | Control | Evidence |
|---|---|---|---|---|---|
| LLM03:2026 / ASI02 | Refund threshold bypass via prompt framing | 0.600 (0.231–0.882), N=5 | **0.000 (0.000–0.161), N=20** | `tool_authorization.rego::refund_threshold_cents` — policy-as-code, unreachable from any prompt | [`phase_a_agent_baseline`](evidence/reports/phase_a_agent_baseline.html) → [`phase_c_highn`](evidence/reports/phase_c_highn.html) |
| LLM02:2026 | Cross-role retrieval, broker → HR documents | 1.000 (0.566–1.000), N=5, deterministic | **0.000 (0.000–0.161), N=20** | `retrieval_authorization.rego` + pre-filter `authorized_search()` | [`phase_a_rag_authorization`](evidence/reports/phase_a_rag_authorization.html) → [`phase_c_rag_highn`](evidence/reports/phase_c_rag_highn.html) |
| ASI06 | Cross-session memory leak | 0.200 (0.036–0.624), N=5 | **0.000 (0.000–0.161), N=20** | Session-scoped, TTL-bounded, provenance-tagged memory | [`phase_a_agent_baseline`](evidence/reports/phase_a_agent_baseline.html) → [`phase_c_highn`](evidence/reports/phase_c_highn.html) |

### The rows that are not wins

Reported at the same prominence, because a table that only shows
successes isn't evidence:

| OWASP 2026 | Attack | Before | After | Honest status |
|---|---|---|---|---|
| LLM01:2026 / ASI01 | `garak` DAN 11.0 jailbreak | 0.500 (0.237–0.763), N=10 | 0.500 (0.237–0.763), N=10 | **Unchanged, still open.** No control in this portfolio targets generic jailbreak resistance. Untrusted-context markers are defense in depth, not a boundary |
| LLM08:2026 | Canary extraction via prefix injection (agent surface) | 1.000 (0.566–1.000), N=5 | 0.000 (0.000–0.434), N=5 | **Looks like the biggest win in the repo; not claimable.** PyRIT doesn't forward a per-trial seed, so the two runs aren't comparable. Left `open`, not promoted to `mitigated` |
| LLM03:2026 | `deepteam` excessive-agency | 0.000 (0.000–0.299), N=9 | — | Never reproduced the vulnerability at all, so there is no before-state to improve on |

The retest runs use N=20 rather than N=5 precisely because a
zero-successes result at N=5 only bounds ASR below 0.434 — not a strong
enough claim to call a fix. See
[`packages/atlas-redteam`](packages/atlas-redteam/README.md) for the
attribution rules that decide when a finding may be promoted to
`mitigated`.

## What's here

| Project | Package | What it does |
|---|---|---|
| 0 | [`atlas`](packages/atlas/README.md) | The target: FastAPI + pgvector RAG + tool-calling agent + MCP servers, with 8 deliberate weaknesses documented in [`WEAKNESSES.md`](packages/atlas/WEAKNESSES.md) and 3 planted canaries |
| 1 | [`atlas-redteam`](packages/atlas-redteam/README.md) | Adversarial evaluation harness wrapping PyRIT, garak, deepteam and promptfoo behind one finding schema, with Wilson CIs, determinism classification, cross-tool dedup, and a regression baseline |
| 2 | [`atlas-retrieval`](packages/atlas-retrieval/README.md) | Retrieval authorization boundary: OPA-backed per-role visibility (pre- and post-filter), trust markers, corpus integrity, PII redaction before embedding, append-only decision log |
| 3 | [`atlas-control`](packages/atlas-control/README.md) | Deterministic control plane: policy-as-code tool authorization, single-use capability tokens, frozen plan-then-execute, budgets, MCP description hash-pinning, staged commits |
| 4 | [`atlas-detect`](packages/atlas-detect/README.md) | OpenTelemetry instrumentation → Collector (flag-then-redact) → ClickHouse, real Sigma rules + stateful detectors, and **measured** precision/recall/MTTD by replaying Project 1's corpus |
| 5 | [`atlas-assurance`](packages/atlas-assurance/README.md) | Evidence pipeline: control register that refuses to assert a control without a linked passing test, evidence-freshness tracking, AIVSS-vs-CVSS scoring, framework crosswalk, CycloneDX AI-BOM |

Shared: [`atlas-schema`](packages/atlas-schema/README.md) — the `Finding`
contract every project reads and writes.

## Detection, measured rather than claimed

Project 4 replayed 45 real attack trials against the live instrumented
stack alongside 65 benign requests
([full dashboard](evidence/reports/atlas_detect_dashboard.html)):

| Detector | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| Retrieval violation *(post-filter mode)* | 5 | 0 | 0 | **1.00** | **1.00** |
| Tool invocation denied | 1 | 0 | 4 | **1.00** | **0.20** |
| Canary in egress path | 0 | 0 | 0 | — | — |
| Memory poisoning | 0 | 25 | 5 | **0.00** | 0.00 |

**Read that table as the deliverable, not as a scoreboard.** Every number
is diagnosable, including the bad ones — which is the entire point. The
alternative, which is what a coverage matrix alone gives you, is four
detectors that look fine and have never caught anything.

- `retrieval_violation` scores **1.00/1.00** in post-filter mode: every
  broker→HR attempt caught, none of 65 benign sessions falsely flagged,
  verified against the live decision log and reproduced on a second run.
  In the **default** pre-filter mode it scores 0.00 — not a defect, but a
  real architectural blind spot: unauthorized chunks are never candidates,
  so no denial is ever logged and there is nothing to observe. Both runs
  are reported rather than only the flattering one.
- The tool-denial detector's 0.20 recall is **model behaviour, not
  detector blindness**. llama3.2 failed to convert "$50,000" into an
  over-threshold `amount_cents` on 4 of 5 attempts. Every genuinely
  over-threshold attempt was caught, with zero false positives — and the
  1/0/4 split reproduced exactly across two independent runs.
- `memory_poisoning` is a genuine **technique mismatch**: the probe tests
  cross-session leakage, the detector looks for within-session
  propagation. Its 25 false positives come from a substring heuristic
  firing on ordinary shared JSON formatting — reported, not tuned away.

Two further detectors were proven firing end to end against the live
stack in the incident walkthroughs (plan deviation at 4.7s, canary in
egress at 11.4s) rather than by corpus replay. The remaining honest gap
is `memory_poisoning`, whose probe pairing doesn't exercise what it
detects.

Eleven of twenty OWASP LLM/ASI categories have no detector mapped at all,
stated plainly in the coverage matrix.

## Assurance

Project 5's [control register](evidence/assurance/control_register.json)
tracks 13 controls, each linked to the specific test that exercises it.
The pipeline raises rather than emitting a claim it can't support:

```python
if not matches:
    raise UnsupportedClaimError(
        f"control {control.control_id!r} declares test_ref={control.test_ref!r}, "
        "but no matching TestResult was ingested — refusing to assert it is effective"
    )
```

Current state: 13 assessed, 0 stale, **8 of 20 OWASP categories with no
control at all**. Reports:
[assurance](evidence/reports/atlas_assurance_report.html) ·
[executive summary](evidence/reports/atlas_assurance_executive_summary.html) ·
[ASR trend](evidence/reports/atlas_assurance_trend.html) ·
[AI-BOM](evidence/assurance/atlas_ai_bom.json).

Framework crosswalks (NIST AI RMF, NIST AI 600-1, ISO/IEC 42001, CSA
AICM, MITRE ATLAS, EU AI Act) are an **engineering aid, not a compliance
determination** — ISO/IEC 42001 certifies a management system, the EU AI
Act regulates a product, and this repo makes no compliance claims.

## Real bugs found by building this

Each was found by running something live, not by reading code, and each
is documented where it was found rather than quietly fixed:

- **Two distinct OPA/Rego bugs.** A float-vs-integer comparison in the
  refund threshold, and — much later, found by Project 4's benign traffic
  — Rego's total type ordering, where *any* string sorts above *any*
  number (`opa eval '"50" > 50000'` → `true`). The second silently denied
  every legitimate refund whenever the model emitted `amount_cents` as a
  JSON string. Neither of atlas-control's 43 tests caught it, because
  they all constructed args with a real int.
- **A Sigma rule with 13.5% precision.** The canary detector matched the
  token in the *outgoing system prompt* — present on every single request
  by design — rather than the model's completion. 64 false positives,
  measured, then fixed.
- **An AI-BOM that was schema-valid and completely unscannable.** The
  generated CycloneDX document validated against the 1.5 schema, and
  `grype` reported "No vulnerabilities found" — while identifying **0 of
  298 components**, because no component carried a PURL. A scanner that
  can't identify anything reports clean, which is the most dangerous
  possible outcome for a supply-chain control. Adding PURLs turned the
  scan real and it immediately found a genuine unfixed Medium
  (`GHSA-w8v5-vhqr-4h9v`, unsafe pickle deserialization in `diskcache`),
  now triaged with written reasoning in [`.grype.yaml`](.grype.yaml).
- **A silently-dead OTel Collector.** ClickHouse's healthcheck probed
  HTTP while the exporter dials the native port, so the collector exited
  at startup and stayed dead while every other service reported healthy —
  exactly the "absent telemetry looks like a healthy system" failure
  Project 4 exists to argue against.
- **Two ground-truth methodology bugs** in detection scoring, where the
  measurement itself was wrong in opposite directions for different probe
  families.
- **Docker networking:** a container attached only to an `internal: true`
  network never gets its `ports:` mapping published, even with a `ports:`
  directive — confirmed by attaching a second network to a *running*
  container and watching the mapping appear mid-flight.

Full lists live in each package's README.

## Running it

Requires Docker, [uv](https://docs.astral.sh/uv/), and
[Ollama](https://ollama.com) with `llama3.2` and `nomic-embed-text`
pulled. `opa` on PATH is needed for the policy tests.

```bash
docker compose -f packages/atlas/docker-compose.yml up -d
uv run --package atlas-redteam atlas-redteam run --suite fast --target http://127.0.0.1:8000
uv run --package atlas-assurance python packages/atlas-assurance/scripts/build_register.py
```

Tests are run per package, scoped to that package's path. The scope
matters: each package declares `asyncio_mode = "auto"` in its own
`pyproject.toml`, and pytest only honors that when the path argument
makes that package's config the active one — an unscoped `pytest` from
the repo root collects all 216 tests but fails every async one.

```bash
uv run --package atlas-control pytest packages/atlas-control
opa test packages/atlas-control/policy
```

## Scope and safety

[`THREAT-MODEL.md`](THREAT-MODEL.md) covers assets, actors, trust
boundaries and which control stands at each one;
[`SECURITY.md`](SECURITY.md) is the policy. In short: every
attack in this repo targets Atlas, a purpose-built local lab
system. `atlas-redteam` enforces a target allowlist in code — it will
refuse to run against a host that isn't the local Atlas instance. The
three planted canaries are computed deterministically at runtime and
never written as literals, and a pre-commit hook blocks any canary value
from entering a commit. Raw transcripts stay gitignored for the same
reason; the findings database and generated reports are what's committed.

## Framework currency

OWASP LLM Top 10 2026 and the Agentic (ASI) Top 10 are living documents,
as is AIVSS v0.8 — re-verify against
[genai.owasp.org](https://genai.owasp.org) and
[aivss.owasp.org](https://aivss.owasp.org) before citing any ID set
externally. Two currency problems were hit while building Project 5 and
are documented there: OWASP's own AIVSS repository disagrees with itself
about what its `AA` metric measures (prose says "Agentic Autonomy", the
executable calculator says "Adversarial Attack Surface"), and the five
"agentic amplification factors" widely attributed to AIVSS v0.8 could not
be verified from a readable primary source, so they are not implemented
as if they had been.

## Not done

No demo video exists yet. A three-minute walkthrough — break something,
show the control, show the retest going green, show the assurance report
updating — is the single highest-value remaining addition, since most
reviewers will watch that and never clone the repo.
