import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/mydb")


def get_conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def init_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id       SERIAL PRIMARY KEY,
                content  TEXT   NOT NULL,
                metadata JSONB,
                embedding vector(1024)
            )
        """)
        # hnsw index works without pre-existing rows (unlike ivfflat)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING hnsw (embedding vector_cosine_ops)
        """)
    conn.commit()
