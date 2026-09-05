package atlas.retrieval_authz

# Retrieval authorization (Project 2): the same "outside the model" policy
# engine Project 3 built for tool execution (tool_authorization.rego),
# extended to cover retrieval. Neither Atlas's prompt-completion path nor
# the LLM is ever consulted about who's allowed to see what — this file is.
#
# input shape:
# {
#   "caller": {"role": "broker"|"adjuster"|"hr"},
#   "chunks": [{"chunk_id": 1, "allowed_roles": ["hr"]}, ...]   # post-filter only
# }
#
# A document's `allowed_roles` is an authorization list (not a single
# owner), so a role's *visibility* is itself a set of allowed_roles values
# it may see — "shared" documents (company bulletins) are visible to more
# than one role without needing per-document special-casing here.
role_visibility := {
	"broker": {"broker", "shared"},
	"adjuster": {"adjuster", "shared"},
	"hr": {"hr"},
}

# PRE-FILTER: the set of allowed_roles values this caller may see, for use
# as a hard SQL filter before the vector search runs. Unknown roles get no
# visibility at all (fail closed) via the default.
default visible_roles := set()

visible_roles := role_visibility[input.caller.role]

# POST-FILTER: given already-retrieved candidate chunks, a decision per
# chunk. Unlike visible_roles, this only ever appears in the response when
# the caller actually sent a `chunks` array (mode="post").
decisions := [decision |
	some chunk in input.chunks
	decision := {
		"chunk_id": chunk.chunk_id,
		"allowed_roles": chunk.allowed_roles,
		"allow": chunk_allowed(chunk),
		"rule": chunk_rule(chunk),
	}
]

# A total function — always true or false, never undefined. chunk_allowed
# is assigned directly into each decision object below; if it were a
# partial/existence rule (the `if {...}` pattern with no else, as used for
# boolean-context-only rules elsewhere in this policy), it would be
# undefined rather than false on denial, which silently drops the entire
# comprehension entry for a denied chunk instead of recording the denial —
# caught live via opa test: a denied HR chunk vanished from `decisions`
# entirely rather than appearing with allow=false.
chunk_allowed(chunk) := true if {
	some r in chunk.allowed_roles
	r in role_visibility[input.caller.role]
} else := false

chunk_rule(chunk) := "role_in_allowed_roles" if {
	chunk_allowed(chunk)
} else := "role_not_permitted"
