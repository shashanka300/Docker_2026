import json
import os

from openai import OpenAI

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "200"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "20"))

client = OpenAI(base_url=LLM_BASE_URL, api_key="not-required")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        i += size - overlap
    return chunks


def _vec_str(v: list[float]) -> str:
    return "[" + ",".join(map(str, v)) + "]"


def embed(text: str) -> list[float]:
    return client.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def ingest(conn, content: str, metadata: dict) -> int:
    chunks = chunk_text(content)
    with conn.cursor() as cur:
        for chunk in chunks:
            vec = embed(chunk)
            cur.execute(
                "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s::jsonb, %s::vector)",
                (chunk, json.dumps(metadata), _vec_str(vec)),
            )
    conn.commit()
    return len(chunks)


def retrieve(conn, query: str, top_k: int = 5) -> list[str]:
    qv = embed(query)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content FROM documents ORDER BY embedding <=> %s::vector LIMIT %s",
            (_vec_str(qv), top_k),
        )
        return [row[0] for row in cur.fetchall()]


def answer(conn, question: str) -> str:
    context = "\n\n---\n\n".join(retrieve(conn, question))
    if not context:
        return "No documents have been ingested yet. Use the Ingest panel to add content first."
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer the question using only the context below. "
                    "If the answer isn't in the context, say so.\n\n"
                    f"Context:\n{context}"
                ),
            },
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content
