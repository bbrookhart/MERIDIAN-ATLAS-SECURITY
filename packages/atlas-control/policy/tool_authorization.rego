package atlas.authz

# Every tool invocation is an authorization request with caller identity,
# tool, arguments, plan context, and current session budget usage. Nothing
# here is reachable from a conversation transcript or a system prompt —
# this file, and only this file, is what "the refund threshold" means.
#
# Monetary values are integer cents, not floats. This isn't just financial
# best practice: the installed OPA build (1.19.0, darwin/arm64) has a real,
# reproducible float-comparison bug — `5000.0 > 500.0` evaluates to `false`
# (confirmed via `opa eval` both with inline literals and a JSON input
# file, so it isn't a shell-quoting artifact) whenever the smaller operand's
# digits are a prefix of the larger operand's. Integer comparison (`5000 >
# 500`) is unaffected. See packages/atlas-control/README.md for the full
# repro.
#
# input shape:
# {
#   "caller": {"role": "broker"|"adjuster"|"hr", "session_id": "..."},
#   "tool": "search_kb"|"lookup_claim"|"issue_refund"|"send_email"|<mcp tool name>,
#   "args": {..., "amount_cents": 40000},
#   "budget": {"tool_calls_used": 0, "refund_cents_used": 0},
#   "limits": {"max_tool_calls_per_session": 20, "max_refund_cents_per_session": 50000}
# }

default allow := false

# The refund threshold. This is the only place it is defined. It is not in
# a system prompt, not an LLM instruction, and not reachable from
# conversation content — moving it requires editing this file and passing
# `opa test`, not persuading a model. $500.00.
refund_threshold_cents := 50000

role_tool_allowlist := {
	"broker": {"search_kb", "lookup_claim"},
	"adjuster": {"search_kb", "lookup_claim", "issue_refund", "send_email"},
	"hr": {"search_kb"},
}

# MCP tools are gated separately from the native-tool role allowlist above:
# every authenticated role may reach the ticketing/docstore MCP surfaces,
# but only after MCP03:2025 tool-poisoning defenses (hash-pinning, done in
# atlas.mcp_client, not here) have already accepted the tool description.
mcp_tools := {"create_ticket", "get_ticket", "list_tickets", "list_documents", "get_document"}

role_permits_tool if input.tool in role_tool_allowlist[input.caller.role]

role_permits_tool if input.tool in mcp_tools

refund_over_threshold if {
	input.tool == "issue_refund"
	input.args.amount_cents > refund_threshold_cents
}

budget_over_session_limit if {
	input.budget.tool_calls_used >= input.limits.max_tool_calls_per_session
}

budget_over_session_limit if {
	input.tool == "issue_refund"
	(input.budget.refund_cents_used + input.args.amount_cents) > input.limits.max_refund_cents_per_session
}

allow if {
	role_permits_tool
	not refund_over_threshold
	not budget_over_session_limit
}

reason := "tool not permitted for role" if {
	not role_permits_tool
} else := "refund exceeds policy threshold" if {
	refund_over_threshold
} else := "session budget exceeded" if {
	budget_over_session_limit
} else := "allowed" if {
	allow
} else := "denied"
