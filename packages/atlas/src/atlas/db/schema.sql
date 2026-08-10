CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id            SERIAL PRIMARY KEY,
    category      TEXT NOT NULL,       -- 'policy' | 'claims' | 'hr'
    owner_role    TEXT NOT NULL,       -- 'broker' | 'adjuster' | 'hr'
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    embedding     VECTOR(768) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);

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
