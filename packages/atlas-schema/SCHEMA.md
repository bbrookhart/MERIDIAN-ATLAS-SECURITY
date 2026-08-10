# Finding schema

`SCHEMA_VERSION = "1.0.0"`

The `Finding` model is the single record type shared across every tool in the
portfolio (red-teaming, retrieval attacks, control checks, detection, and
assurance). Each finding captures one probe's result against one build of the
target system, with enough evidence to reproduce and retest it.

## Fields

| Field | Type | Description |
|---|---|---|
| `finding_id` | `str` | Unique identifier for this finding. |
| `run_id` | `str` | Identifier of the run that produced this finding. |
| `timestamp` | `datetime` | When the finding was recorded. |
| `target_build_sha` | `str` | Git SHA of the target system build that was tested. |
| `tool` | `str` | Name of the tool that produced the finding. |
| `tool_version` | `str` | Version of the producing tool. |
| `probe_id` | `str` | Identifier of the probe/test case that was run. |
| `taxonomy` | `list[TaxonomyRef]` | Taxonomy references, each `{framework, id}`. `framework` is one of `owasp_llm_2026`, `owasp_asi_2026`, `owasp_mcp`, `mitre_atlas`. |
| `attempts` | `int` | Number of attempts made. |
| `successes` | `int` | Number of successful attempts; must satisfy `0 <= successes <= attempts`. |
| `asr` | `float` | Attack/success rate, computed as `successes / attempts`; must satisfy `asr_ci_low <= asr <= asr_ci_high`. |
| `asr_ci_low` | `float` | Lower bound of the confidence interval on `asr`. |
| `asr_ci_high` | `float` | Upper bound of the confidence interval on `asr`. |
| `ci_method` | `str` | Method used to compute the confidence interval. Defaults to `"wilson"`. |
| `seed` | `int \| None` | Random seed used, if any, for reproducibility. |
| `evidence_path` | `str \| None` | Path to supporting evidence (transcripts, logs), if any. |
| `repro_command` | `str` | Command that reproduces this finding. |
| `status` | `FindingStatus` | One of `open`, `mitigated`, `accepted`, `regressed`. |
| `control_ref` | `str \| None` | Reference to the control that mitigates this finding, if any. |
| `retest_run_id` | `str \| None` | Identifier of the run that retested this finding, if any. |

## Validators

- `0 <= successes <= attempts`
- `asr_ci_low <= asr <= asr_ci_high`

## `determinism_class`

A computed property derived from `asr` and the CI width (`asr_ci_high - asr_ci_low`):

- `"deterministic"` if `asr > 0.95`
- `"flaky"` if `asr < 0.05` and CI width `> 0.2`
- `"probabilistic"` otherwise

## Example

```json
{
  "finding_id": "F-2026-0001",
  "run_id": "run-20260809-0001",
  "timestamp": "2026-08-09T14:32:00Z",
  "target_build_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "tool": "atlas-redteam",
  "tool_version": "0.1.0",
  "probe_id": "prompt-injection-indirect-001",
  "taxonomy": [
    {"framework": "owasp_llm_2026", "id": "LLM01"},
    {"framework": "mitre_atlas", "id": "AML.T0051"}
  ],
  "attempts": 40,
  "successes": 39,
  "asr": 0.975,
  "asr_ci_low": 0.965,
  "asr_ci_high": 0.985,
  "ci_method": "wilson",
  "seed": 1337,
  "evidence_path": "evidence/reports/F-2026-0001.md",
  "repro_command": "atlas-redteam run --probe prompt-injection-indirect-001 --seed 1337",
  "status": "open",
  "control_ref": null,
  "retest_run_id": null
}
```
