CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id        SERIAL PRIMARY KEY,
    content   TEXT   NOT NULL,
    metadata  JSONB,
    embedding vector(1024)
);

-- hnsw is preferred over ivfflat for small datasets — no row count requirement
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents USING hnsw (embedding vector_cosine_ops);
