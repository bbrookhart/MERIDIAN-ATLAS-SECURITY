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

CREATE TABLE IF NOT EXISTS agent_memory (
    id            SERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,       -- 'user_message' | 'assistant_message' | 'tool_result'
    content       TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
