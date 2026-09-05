NATIVE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_claim",
            "description": "Look up a Meridian Mutual insurance claim by its claim number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_number": {
                        "type": "string",
                        "description": "The claim number, e.g. CLM-00042.",
                    }
                },
                "required": ["claim_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Issue a refund to a policyholder for a given claim.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_number": {"type": "string"},
                    "amount": {
                        "type": "number",
                        "description": "Refund amount in USD.",
                    },
                },
                "required": ["claim_number", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": (
                "Search Meridian Mutual's internal knowledge base "
                "(policy documents, claims notes, HR material)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]
