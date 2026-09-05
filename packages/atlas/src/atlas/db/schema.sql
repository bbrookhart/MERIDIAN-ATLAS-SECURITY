CREATE EXTENSION IF NOT EXISTS vector;

-- Project 2 (LLM02:2026 — Sensitive Information Disclosure): every chunk
-- carries its own permission mirror, provenance, and integrity hash.
-- `owner_role` is retained as the category/provenance label; `allowed_roles`
-- is the actual authorization list atlas-control's retrieval policy
-- evaluates against — a document can be visible to more than one role
-- (see the 'shared' category in seed.py), which owner_role alone can't
-- express. `tenant_id` defaults to the single tenant this deployment
-- actually has; the column exists so the authorization model doesn't have
-- to change shape if that stops being true, not as a claim of real
-- multi-tenancy today.
CREATE TABLE IF NOT EXISTS documents (
    id                          SERIAL PRIMARY KEY,
    category                    TEXT NOT NULL,       -- 'policy' | 'claims' | 'hr' | 'shared'
    owner_role                  TEXT NOT NULL,       -- 'broker' | 'adjuster' | 'hr'
    allowed_roles               TEXT[] NOT NULL,     -- authorization list, evaluated by atlas-control
    tenant_id                   TEXT NOT NULL DEFAULT 'meridian-mutual',
    title                       TEXT NOT NULL,
    body                        TEXT NOT NULL,
    embedding                   VECTOR(768) NOT NULL,
    source_doc_id               TEXT,
    source_system_acl_snapshot  JSONB,
    content_sha256              TEXT NOT NULL,       -- verified at retrieval; a mismatch means
                                                       -- something wrote to this row outside ingestion
    ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingest_run_id               TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);

CREATE INDEX IF NOT EXISTS documents_allowed_roles_idx
    ON documents USING GIN (allowed_roles);

-- Retrieval decision log (Project 2, headline deliverable): an append-only,
-- queryable record of every /rag/query call — EU AI Act Article 12
-- record-keeping evidence. Never updated except to attach response_hash
-- once the chat completion the retrieval fed into has actually happened.
CREATE TABLE IF NOT EXISTS retrieval_decisions (
    id                    SERIAL PRIMARY KEY,
    request_id            UUID NOT NULL,
    occurred_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    caller_role           TEXT NOT NULL,
    caller_session_id     TEXT,
    query_hash            TEXT NOT NULL,       -- sha256 of the raw query text, never the text itself
    mode                  TEXT NOT NULL,       -- 'none' (pre-Project-2) | 'pre' | 'post'
    candidate_chunk_ids   INT[] NOT NULL,
    decisions             JSONB NOT NULL,      -- [{chunk_id, allowed_roles, allow, rule}]
    context_chunk_ids     INT[] NOT NULL,      -- ids that actually entered the prompt
    redactions_applied    JSONB NOT NULL DEFAULT '[]',
    response_hash         TEXT
);

CREATE INDEX IF NOT EXISTS retrieval_decisions_occurred_idx ON retrieval_decisions (occurred_at);
CREATE INDEX IF NOT EXISTS retrieval_decisions_role_idx ON retrieval_decisions (caller_role);

-- Permission-change webhook staleness (Project 2): last time a permission
-- event was received vs. last time matching documents were actually
-- re-stamped, per source_doc_id. In this synchronous implementation the
-- gap is a genuine lower bound, not a claim about a real async pipeline.
CREATE TABLE IF NOT EXISTS permission_sync_events (
    id                      SERIAL PRIMARY KEY,
    source_doc_id           TEXT NOT NULL,
    new_allowed_roles       TEXT[] NOT NULL,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    chunks_restamped_at     TIMESTAMPTZ,
    chunks_restamped_count  INT NOT NULL DEFAULT 0
);

-- Memory provenance (Project 3 / ASI06): every stored fact carries its
-- source, trust tier, an ingest run id, and a TTL. load_recent_facts()
-- filters by session_id — the fix for the cross-session leak Project 3's
-- Phase A red-team run demonstrated live (see agent-baseline suite).
CREATE TABLE IF NOT EXISTS agent_memory (
    id            SERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,       -- 'user_message' | 'assistant_message' | 'tool_result'
    content       TEXT NOT NULL,
    source        TEXT NOT NULL,       -- 'user_input' | 'assistant_output' | 'tool_result'
    trust_tier    TEXT NOT NULL,       -- 'trusted' | 'untrusted'
    run_id        TEXT NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_memory_session_idx ON agent_memory (session_id);
