"""Parsers for real, CI-producible evidence artifacts.

Nothing in this package invents a test outcome — each parser turns one
genuine tool output format (`pytest --junitxml`, `opa test --format
json`) into `atlas_assurance.models.TestResult`.
"""
