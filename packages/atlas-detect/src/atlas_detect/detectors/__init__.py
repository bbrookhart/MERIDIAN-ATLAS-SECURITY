"""Stateful detectors — Sigma's flat field-equals-value model doesn't fit
these: each one either correlates two events across time (memory
poisoning), needs a learned baseline (tool-sequence anomaly), aggregates
across a session (cost asymmetry), or reads a different data source
entirely (retrieval violations, from Atlas's own decision log, not
ClickHouse). Each module exposes a `detect(...)` function and is covered
by its own test in packages/atlas-detect/tests/.
"""
