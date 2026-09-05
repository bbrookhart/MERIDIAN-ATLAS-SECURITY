from atlas.routers.agent import NATIVE_TOOL_NAMES
from atlas.tools.schemas import NATIVE_TOOL_SCHEMAS


def test_native_tool_schemas_match_dispatch_table():
    schema_names = {t["function"]["name"] for t in NATIVE_TOOL_SCHEMAS}
    assert schema_names == NATIVE_TOOL_NAMES


def test_every_schema_has_required_fields():
    for tool in NATIVE_TOOL_SCHEMAS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["name"]
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert "required" in fn["parameters"]
