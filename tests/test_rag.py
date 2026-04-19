"""Unit tests — no Docker or external services required."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.rag import chunk_text


# ── chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_basic():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, size=10, overlap=2)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 10 for c in chunks)


def test_chunk_text_overlap():
    text = " ".join(str(i) for i in range(20))
    chunks = chunk_text(text, size=5, overlap=2)
    # last word of chunk N must reappear at the start of chunk N+1
    last_word = chunks[0].split()[-1]
    assert last_word in chunks[1].split()


def test_chunk_text_short_input():
    assert chunk_text("hello world", size=400, overlap=50) == ["hello world"]


def test_chunk_text_empty():
    assert chunk_text("") == []


# ── RAG functions ─────────────────────────────────────────────────────────────

FAKE_VEC = [0.1] * 1024


def _mock_conn(rows=None):
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = rows or []
    cur.fetchone.return_value = (0,)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def test_retrieve_returns_chunks():
    conn, cur = _mock_conn(rows=[("chunk about Docker",), ("chunk about RAG",)])
    with patch("app.rag.embed", return_value=FAKE_VEC):
        from app.rag import retrieve
        results = retrieve(conn, "What is Docker?", top_k=2)
    assert results == ["chunk about Docker", "chunk about RAG"]
    cur.execute.assert_called_once()


def test_retrieve_empty_db():
    conn, _ = _mock_conn(rows=[])
    with patch("app.rag.embed", return_value=FAKE_VEC):
        from app.rag import retrieve
        assert retrieve(conn, "anything") == []


def test_answer_no_docs_returns_fallback():
    conn, _ = _mock_conn(rows=[])
    with patch("app.rag.embed", return_value=FAKE_VEC):
        from app.rag import answer
        result = answer(conn, "What is Docker?")
    assert "No documents" in result


def test_answer_with_context_calls_llm():
    conn, _ = _mock_conn(rows=[("pgvector stores vectors",)])
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "pgvector is a Postgres extension."
    with (
        patch("app.rag.embed", return_value=FAKE_VEC),
        patch("app.rag.client") as mock_client,
    ):
        mock_client.chat.completions.create.return_value = mock_resp
        from app.rag import answer
        result = answer(conn, "What is pgvector?")
    assert result == "pgvector is a Postgres extension."
    mock_client.chat.completions.create.assert_called_once()


# ── FastAPI endpoints ─────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    with (
        patch("app.db.get_conn") as mock_get,
        patch("app.db.init_schema"),
    ):
        conn, _ = _mock_conn()
        mock_get.return_value = conn
        from app.main import app
        with TestClient(app) as c:
            yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_stats(client):
    with patch("app.main.get_conn") as mock_get:
        conn, cur = _mock_conn()
        cur.fetchone.return_value = (7,)
        mock_get.return_value = conn
        r = client.get("/stats")
    assert r.status_code == 200
    assert r.json()["document_chunks"] == 7


def test_ingest_requires_content(client):
    r = client.post("/ingest", data={})
    assert r.status_code == 400


def test_ingest_text(client):
    with (
        patch("app.main.get_conn") as mock_get,
        patch("app.main.ingest", return_value=3) as mock_ingest,
    ):
        conn, _ = _mock_conn()
        mock_get.return_value = conn
        r = client.post("/ingest", data={"text": "some content", "source": "test"})
    assert r.status_code == 200
    assert r.json()["chunks_ingested"] == 3
    mock_ingest.assert_called_once()


def test_ingest_sample(client, tmp_path):
    sample = tmp_path / "docker-ai-guide.md"
    sample.write_text("Docker is a containerisation tool.")
    with (
        patch("app.main.get_conn") as mock_get,
        patch("app.main.ingest", return_value=1) as mock_ingest,
        patch("app.main.SAMPLE_DOC", sample),
    ):
        conn, _ = _mock_conn()
        mock_get.return_value = conn
        r = client.post("/ingest/sample")
    assert r.status_code == 200
    assert r.json()["chunks_ingested"] == 1
    assert r.json()["source"] == "docker-ai-guide.md"
    mock_ingest.assert_called_once()


def test_ingest_sample_missing(client, tmp_path):
    with patch("app.main.SAMPLE_DOC", tmp_path / "missing.md"):
        r = client.post("/ingest/sample")
    assert r.status_code == 404


def test_query_endpoint(client):
    with (
        patch("app.main.get_conn") as mock_get,
        patch("app.main.answer", return_value="Containers share the host OS kernel."),
    ):
        conn, _ = _mock_conn()
        mock_get.return_value = conn
        r = client.post("/query", json={"question": "What is a container?"})
    assert r.status_code == 200
    assert "kernel" in r.json()["answer"]
