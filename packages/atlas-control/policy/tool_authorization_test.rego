package atlas.authz_test

import data.atlas.authz

base_budget := {"tool_calls_used": 0, "refund_cents_used": 0}
base_limits := {"max_tool_calls_per_session": 20, "max_refund_cents_per_session": 50000}

test_adjuster_can_issue_refund_within_threshold if {
	authz.allow with input as {
		"caller": {"role": "adjuster", "session_id": "s1"},
		"tool": "issue_refund",
		"args": {"claim_number": "CLM-1", "amount_cents": 40000},
		"budget": base_budget,
		"limits": base_limits,
	}
}

# The load-bearing test: no matter what a conversation transcript, a system
# prompt, or a "manager override" claim in the request says, an amount over
# the threshold is denied. There is no field in `input` that represents
# "the model was persuaded" — the policy has nothing to be persuaded by.
test_refund_over_threshold_is_denied_regardless_of_framing if {
	over_threshold_input := {
		"caller": {"role": "adjuster", "session_id": "s1"},
		"tool": "issue_refund",
		"args": {"claim_number": "CLM-1", "amount_cents": 5000000},
		"budget": base_budget,
		"limits": base_limits,
	}
	not authz.allow with input as over_threshold_input
	authz.reason == "refund exceeds policy threshold" with input as over_threshold_input
}

test_refund_at_exact_threshold_is_allowed if {
	authz.allow with input as {
		"caller": {"role": "adjuster", "session_id": "s1"},
		"tool": "issue_refund",
		"args": {"claim_number": "CLM-1", "amount_cents": 50000},
		"budget": base_budget,
		"limits": base_limits,
	}
}

test_broker_cannot_issue_refund_even_within_threshold if {
	not authz.allow with input as {
		"caller": {"role": "broker", "session_id": "s1"},
		"tool": "issue_refund",
		"args": {"claim_number": "CLM-1", "amount_cents": 10000},
		"budget": base_budget,
		"limits": base_limits,
	}
}

test_hr_can_only_search_kb if {
	authz.allow with input as {
		"caller": {"role": "hr", "session_id": "s1"},
		"tool": "search_kb",
		"args": {"query": "policy"},
		"budget": base_budget,
		"limits": base_limits,
	}
	not authz.allow with input as {
		"caller": {"role": "hr", "session_id": "s1"},
		"tool": "lookup_claim",
		"args": {"claim_number": "CLM-1"},
		"budget": base_budget,
		"limits": base_limits,
	}
}

test_session_tool_call_budget_exhausted_denies_further_calls if {
	not authz.allow with input as {
		"caller": {"role": "adjuster", "session_id": "s1"},
		"tool": "search_kb",
		"args": {"query": "x"},
		"budget": {"tool_calls_used": 20, "refund_cents_used": 0},
		"limits": base_limits,
	}
}

test_cumulative_refund_budget_blocks_second_refund_even_if_each_is_under_threshold if {
	not authz.allow with input as {
		"caller": {"role": "adjuster", "session_id": "s1"},
		"tool": "issue_refund",
		"args": {"claim_number": "CLM-2", "amount_cents": 20000},
		"budget": {"tool_calls_used": 1, "refund_cents_used": 40000},
		"limits": base_limits,
	}
}

test_mcp_tools_available_to_any_authenticated_role if {
	authz.allow with input as {
		"caller": {"role": "broker", "session_id": "s1"},
		"tool": "list_tickets",
		"args": {},
		"budget": base_budget,
		"limits": base_limits,
	}
}

test_unknown_tool_is_denied if {
	not authz.allow with input as {
		"caller": {"role": "adjuster", "session_id": "s1"},
		"tool": "delete_database",
		"args": {},
		"budget": base_budget,
		"limits": base_limits,
	}
}
