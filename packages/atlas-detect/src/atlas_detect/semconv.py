"""GenAI semantic convention attribute names — pinned, not re-derived per
call site.

`opentelemetry-semantic-conventions` is pinned to **0.65b0** in this
package's `pyproject.toml`. Verified by downloading and inspecting that
exact wheel during Project 4's planning: every constant in
`opentelemetry.semconv._incubating.attributes.gen_ai_attributes` is marked
"Deprecated: moved to the OpenTelemetry GenAI semantic conventions
repository" — i.e. the GenAI conventions are still incubating and have
already moved once upstream. This is the real, current state of the spec,
not a guess: pin the version, expect the names to move again, and don't
scatter literal `"gen_ai.*"` strings across the codebase so a future
version bump is a one-file change.

A newer contrib package, `opentelemetry-util-genai` 1.0b0, offers a
higher-level `TelemetryHandler`/`InferenceInvocation` lifecycle API built
on these same incubating attributes. It was evaluated and not used here:
its default posture puts message content behind an opt-in environment
variable for span *attributes*, which is the opposite of the
events-not-attributes decision this project needs to make and demonstrate
explicitly (see `spans.py`). Building directly on the stable
`opentelemetry-sdk` API, using only the attribute-name constants below,
keeps that decision visible in this project's own code instead of buried
in a dependency's defaults.
"""

from __future__ import annotations

from opentelemetry.semconv._incubating.attributes import gen_ai_attributes as _gen_ai

SEMCONV_VERSION = "0.65b0"

# Operation names (gen_ai.operation.name) — verified against the
# installed GenAiOperationNameValues enum's actual string values, not
# hand-typed guesses.
OP_CHAT = _gen_ai.GenAiOperationNameValues.CHAT.value
OP_RETRIEVAL = _gen_ai.GenAiOperationNameValues.RETRIEVAL.value
OP_EXECUTE_TOOL = _gen_ai.GenAiOperationNameValues.EXECUTE_TOOL.value
OP_INVOKE_AGENT = _gen_ai.GenAiOperationNameValues.INVOKE_AGENT.value
OP_EMBEDDINGS = _gen_ai.GenAiOperationNameValues.EMBEDDINGS.value

ATTR_OPERATION_NAME = _gen_ai.GEN_AI_OPERATION_NAME
ATTR_REQUEST_MODEL = _gen_ai.GEN_AI_REQUEST_MODEL
ATTR_REQUEST_SEED = _gen_ai.GEN_AI_REQUEST_SEED
ATTR_RESPONSE_MODEL = "gen_ai.response.model"
ATTR_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
ATTR_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
ATTR_TOOL_NAME = "gen_ai.tool.name"
ATTR_DATA_SOURCE_ID = _gen_ai.GEN_AI_DATA_SOURCE_ID
ATTR_PROVIDER_NAME = _gen_ai.GEN_AI_PROVIDER_NAME
ATTR_CONVERSATION_ID = _gen_ai.GEN_AI_CONVERSATION_ID

# Project-specific attributes (not part of GenAI semconv — this portfolio's
# own security-relevant dimensions, namespaced under atlas.* to avoid
# colliding with a future semconv version that adds these names upstream).
ATTR_ATLAS_ROLE = "atlas.caller_role"
ATTR_ATLAS_SESSION_ID = "atlas.session_id"
ATTR_ATLAS_RETRIEVAL_MODE = "atlas.retrieval.mode"
ATTR_ATLAS_RETRIEVED_CHUNK_IDS = "atlas.retrieval.chunk_ids"
ATTR_ATLAS_POLICY_ALLOW = "atlas.policy.allow"
ATTR_ATLAS_POLICY_RULE = "atlas.policy.rule"
ATTR_ATLAS_POLICY_TOOL = "atlas.policy.tool"

# Event names. Prompt/completion content is ALWAYS an event, never an
# attribute — see spans.py for the single choke point that enforces this.
EVENT_PROMPT = "gen_ai.content.prompt"
EVENT_COMPLETION = "gen_ai.content.completion"
