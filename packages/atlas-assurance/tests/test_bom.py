import json

from atlas_assurance.bom import build_bom, emit_cyclonedx_json, normalize_for_drift_check
from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator


def test_build_bom_produces_valid_cyclonedx_1_5_json() -> None:
    bom = build_bom()
    output = emit_cyclonedx_json(bom)

    errors = JsonStrictValidator(SchemaVersion.V1_5).validate_str(output)

    assert errors is None


def test_bom_includes_both_real_ollama_models() -> None:
    bom_json = json.loads(emit_cyclonedx_json(build_bom()))

    names = {c["name"] for c in bom_json["components"] if c["type"] == "machine-learning-model"}

    assert names == {"llama3.2", "nomic-embed-text"}


def test_bom_includes_both_mcp_servers_with_tool_hashes() -> None:
    bom_json = json.loads(emit_cyclonedx_json(build_bom()))

    services = {s["name"]: s for s in bom_json["services"]}

    assert set(services) == {"atlas-docstore", "atlas-ticketing"}
    docstore_hashes = [
        p for p in services["atlas-docstore"]["properties"] if "tool_hash" in p["name"]
    ]
    assert len(docstore_hashes) == 2  # list_documents, get_document
    assert all(len(p["value"]) == 64 for p in docstore_hashes)  # sha256 hex digest length


def test_bom_includes_a_large_real_transitive_dependency_set() -> None:
    bom_json = json.loads(emit_cyclonedx_json(build_bom()))

    libraries = [c for c in bom_json["components"] if c["type"] == "library"]

    assert len(libraries) > 250  # this repo's real uv.lock has 290+ resolved packages
    names = {c["name"] for c in libraries}
    assert "fastapi" in names
    assert "duckdb" in names


def test_normalize_for_drift_check_ignores_random_bom_ref_and_serial_number() -> None:
    bom_json_a = json.loads(emit_cyclonedx_json(build_bom()))
    bom_json_b = json.loads(emit_cyclonedx_json(build_bom()))

    assert bom_json_a["serialNumber"] != bom_json_b["serialNumber"]  # random per generation
    assert normalize_for_drift_check(bom_json_a) == normalize_for_drift_check(bom_json_b)


def test_normalize_for_drift_check_detects_a_real_component_removal() -> None:
    bom_json = json.loads(emit_cyclonedx_json(build_bom()))
    before = normalize_for_drift_check(bom_json)

    bom_json["components"] = [c for c in bom_json["components"] if c["name"] != "fastapi"]
    after = normalize_for_drift_check(bom_json)

    assert before != after
