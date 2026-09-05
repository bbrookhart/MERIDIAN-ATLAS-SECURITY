"""Adapter protocol: one module per red-team tool.

Each adapter exposes `run(target, probe_cfg) -> ProbeRun` (see
atlas_redteam.findings.ProbeRun) by driving the tool's own published
probes/attacks against Atlas and judging success with the tool's own
detectors/scorers — no novel attack payloads are authored here, only
orchestration and result parsing.

Every adapter's *parsing* logic (native tool output -> ProbeRun) is
independently unit-testable against a recorded fixture in tests/fixtures/,
so CI never needs a live model call to verify an adapter is wired
correctly.
"""
