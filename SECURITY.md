# Security policy

## What this repository is

`meridian-atlas-security` is a **security research and demonstration
lab**. It deliberately contains a vulnerable application (`packages/atlas`)
whose weaknesses are documented on purpose in
[`packages/atlas/WEAKNESSES.md`](packages/atlas/WEAKNESSES.md).

**Do not deploy Atlas, or any part of this repository, to a production or
internet-reachable environment.** It is designed to be exploitable. It
ships with intentionally weak defaults, and several weaknesses are still
open by design so that later projects have something real to detect.

See [`THREAT-MODEL.md`](THREAT-MODEL.md) for the assets, actors, trust
boundaries and controls this system is designed around.

## Reporting a vulnerability

Vulnerabilities in the *intentionally vulnerable* target
(`packages/atlas`) are not security issues — they are the subject matter.
Check `WEAKNESSES.md` first.

Genuine issues worth reporting are ones where this repository could harm
someone running it as intended, for example:

- A control in `atlas-control`, `atlas-retrieval`, `atlas-detect` or
  `atlas-assurance` that does not actually enforce what it claims to.
- The red-team harness (`atlas-redteam`) attacking a host outside its
  allowlist, or otherwise escaping its intended scope.
- A canary value, credential, or captured transcript leaking into the git
  history.
- Anything in the evidence pipeline that emits a control assertion with
  no linked, real, passing test.

Please open a GitHub issue. This is a portfolio project with no SLA — do
not expect a coordinated-disclosure process.

## Safety controls in this repository

These are enforced in code, not by convention:

| Control | Where |
|---|---|
| Red-team target allowlist, fails closed | `packages/atlas-redteam/src/atlas_redteam/target.py` |
| Canary values computed at runtime, never written as literals | `packages/atlas/src/atlas/canaries.py` |
| Pre-commit hook blocking canary values from any staged diff | `.pre-commit-config.yaml` |
| Raw transcripts gitignored (they contain canaries) | `.gitignore` |
| Secret scanning on every commit (gitleaks) | `.pre-commit-config.yaml` |
| Dependency vulnerability scanning against the AI-BOM | `.github/workflows/ci.yml` |
| No assertion without linked passing evidence | `packages/atlas-assurance/src/atlas_assurance/evidence_store.py` |

## Credentials in this repository

The `atlas:atlas` database credentials and the ClickHouse password in
`packages/atlas/docker-compose.yml` are **lab-only, intentionally
committed**, and bound to loopback. They exist so the stack comes up with
one command. They grant access to nothing but a local container holding
synthetic data. No real credential, API key, or token is committed
anywhere; `gitleaks` runs on every commit to keep it that way.

## Synthetic data only

Every document, claim, ticket and customer in this repository is
synthetic and generated deterministically from a fixed seed
(`packages/atlas/src/atlas/seed.py`). No real personal data, no real
insurance records, and no real organization's data are present. "Meridian
Mutual" is a fictional insurer.
