"""Unit tests — no Docker or external services required."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── chunk_text ────────────────────────────────────────────────────────────────

from app.rag import chunk_text


def test_chunk_text_basic():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, size=10, overlap=2)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 10 for c in chunks)


def test_chunk_text_overlap():
    text = " ".join(str(i) for i in range(20))
    chunks = chunk_text(text, size=5, overlap=2)
    # With overlap, last word of chunk N should appear near start of chunk N+1
    last_word = chunks[0].split()[-1]
    second_chunk_words = chunks[1].split()
    assert last_word in second_chunk_words


def test_chunk_text_short_input():
    text = "hello world"
    chunks = chunk_text(text, size=400, overlap=50)
    assert chunks == ["hello world"]


def test_chunk_text_empty():
    assert chunk_text("") == []


# ── FastAPI endpoints ─────────────────────────────────────────────────────────

def _make_mock_conn():
    """Return a mock psycopg connection + cursor."""
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = (42,)
    cur.fetchall.return_value = []
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


@pytest.fixture()
def client():
    with (
        patch("app.db.get_conn") as mock_get,
        patch("app.db.init_schema"),
    ):
        conn, _ = _make_mock_conn()
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
        conn, cur = _make_mock_conn()
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
        conn, _ = _make_mock_conn()
        mock_get.return_value = conn
        r = client.post("/ingest", data={"text": "some content", "source": "test"})
    assert r.status_code == 200
    assert r.json()["chunks_ingested"] == 3
    mock_ingest.assert_called_once()


def test_query_endpoint(client):
    with (
        patch("app.main.get_conn") as mock_get,
        patch("app.main.answer", return_value="42") as mock_answer,
    ):
        conn, _ = _make_mock_conn()
        mock_get.return_value = conn
        r = client.post("/query", json={"question": "What is Docker?"})
    assert r.status_code == 200
    assert r.json()["answer"] == "42"
    mock_answer.assert_called_once()
