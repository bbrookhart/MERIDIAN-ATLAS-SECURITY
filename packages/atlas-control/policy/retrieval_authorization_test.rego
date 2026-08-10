package atlas.retrieval_authz_test

import data.atlas.retrieval_authz

test_broker_visible_roles_include_shared_not_hr if {
	retrieval_authz.visible_roles == {"broker", "shared"} with input as {"caller": {"role": "broker"}}
}

test_hr_visible_roles_are_hr_only if {
	retrieval_authz.visible_roles == {"hr"} with input as {"caller": {"role": "hr"}}
}

test_unknown_role_has_no_visibility if {
	retrieval_authz.visible_roles == set() with input as {"caller": {"role": "vendor"}}
}

test_postfilter_allows_shared_chunk_for_broker_and_adjuster if {
	broker_input := {
		"caller": {"role": "broker"},
		"chunks": [{"chunk_id": 1, "allowed_roles": ["broker", "adjuster"]}],
	}
	retrieval_authz.decisions == [{
		"chunk_id": 1,
		"allowed_roles": ["broker", "adjuster"],
		"allow": true,
		"rule": "role_in_allowed_roles",
	}] with input as broker_input
}

test_postfilter_denies_hr_chunk_for_broker if {
	broker_input := {
		"caller": {"role": "broker"},
		"chunks": [{"chunk_id": 2, "allowed_roles": ["hr"]}],
	}
	retrieval_authz.decisions == [{
		"chunk_id": 2,
		"allowed_roles": ["hr"],
		"allow": false,
		"rule": "role_not_permitted",
	}] with input as broker_input
}

# The load-bearing test: this is the exact scenario Project 2's before-state
# proved live (a broker query returning 5/5 HR chunks as candidates,
# ASR=1.0 in phase_a_rag_authorization). Post-hardening, every one of those
# candidate chunks must decide "not allowed" here, regardless of how the
# query was phrased — there is nothing in `input` that represents "the
# model was persuaded" or "the query looked legitimate".
test_hr_content_is_denied_to_broker_regardless_of_chunk_count if {
	broker_input := {
		"caller": {"role": "broker"},
		"chunks": [
			{"chunk_id": 1, "allowed_roles": ["hr"]},
			{"chunk_id": 2, "allowed_roles": ["hr"]},
			{"chunk_id": 3, "allowed_roles": ["hr"]},
		],
	}
	result := retrieval_authz.decisions with input as broker_input
	every d in result {
		d.allow == false
	}
}

test_mixed_candidate_set_only_authorized_chunks_pass if {
	adjuster_input := {
		"caller": {"role": "adjuster"},
		"chunks": [
			{"chunk_id": 1, "allowed_roles": ["adjuster"]},
			{"chunk_id": 2, "allowed_roles": ["hr"]},
			{"chunk_id": 3, "allowed_roles": ["broker", "adjuster"]},
		],
	}
	result := retrieval_authz.decisions with input as adjuster_input
	allowed_ids := {d.chunk_id | some d in result; d.allow}
	allowed_ids == {1, 3}
}
