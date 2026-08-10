from atlas_detect.semconv import ATTR_OPERATION_NAME, SEMCONV_VERSION


def test_semconv_version_is_pinned():
    assert SEMCONV_VERSION == "0.65b0"


def test_operation_name_attribute_matches_installed_incubating_semconv():
    """Guards against silently drifting from the installed
    opentelemetry-semantic-conventions package's actual constant value —
    if a version bump renames this, this test catches it before a
    detector silently stops matching gen_ai.operation.name."""
    assert ATTR_OPERATION_NAME == "gen_ai.operation.name"
