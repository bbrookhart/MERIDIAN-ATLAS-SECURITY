# atlas-schema

The contract every other package in the portfolio reads and writes. It is
deliberately tiny and has exactly one heavyweight dependency (`pydantic`),
because everything else depends on it — including packages that must not
inherit the red-team toolchain.

## `Finding`

One probe's measured result against one build of Atlas. Produced by
[`atlas-redteam`](../atlas-redteam/README.md), stored in
`evidence/findings.duckdb`, and consumed by
[`atlas-assurance`](../atlas-assurance/README.md).

| Field | Why it exists |
|---|---|
| `finding_id`, `run_id`, `timestamp`, `target_build_sha` | Every claim traces to a specific run against a specific build |
| `tool`, `tool_version`, `probe_id` | Which published tool produced it, at what version |
| `taxonomy: list[TaxonomyRef]` | OWASP LLM 2026 / ASI / MCP / MITRE ATLAS IDs — a finding can map to several |
| `attempts`, `successes`, `asr` | The raw counts, not just the rate |
| `asr_ci_low`, `asr_ci_high`, `ci_method` | Wilson 95% CI. A rate without an interval isn't a measurement |
| `seed` | Nullable on purpose — some adapters don't forward one, and pretending otherwise would make runs look comparable when they aren't |
| `evidence_path`, `repro_command` | Someone else has to be able to reproduce it |
| `status`, `control_ref`, `retest_run_id` | Links a finding to the control that fixed it and the retest that proved it |

Two model validators reject impossible data at construction:
`0 <= successes <= attempts`, and `asr` must fall inside its own
confidence interval.

`determinism_class` is computed, not stored — `deterministic` above 0.95
ASR, `flaky` for a near-zero rate with a wide interval, `probabilistic`
otherwise. It's the difference between "we fixed it" and "we didn't
happen to reproduce it this time."

See [`SCHEMA.md`](SCHEMA.md) for the authoritative field documentation and
a worked JSON example.

## `atlas_schema.taxonomy`

The canonical OWASP LLM 2026 and Agentic (ASI) 2026 ID→name tables.

These live here rather than in any one project because four packages need
them and only one has any business depending on red-team tooling.
`atlas-assurance` used to import them from `atlas_redteam.coverage`, which
made garak, PyRIT and deepteam — and through PyRIT, the whole
torch/transformers tree — runtime dependencies of the assurance pipeline,
to read twenty strings. Moving the tables here removed that entirely
(verified: `uv tree --package atlas-assurance --no-dev` matches zero of
those packages).

Both ID sets are living documents. Re-verify against
[genai.owasp.org](https://genai.owasp.org) before citing them externally.

## Usage

```bash
uv run --package atlas-schema pytest packages/atlas-schema
```
