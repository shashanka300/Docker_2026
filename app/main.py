from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import get_conn, init_schema
from app.rag import answer, ingest

SAMPLE_DOC = Path("docs/docker-ai-guide.md")
STATIC_DIR = Path("app/static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_conn()
    try:
        init_schema(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Docker AI Demo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/ingest")
async def ingest_endpoint(
    file: UploadFile = File(None),
    text: str = Form(None),
    source: str = Form("upload"),
):
    if file and file.filename:
        content = (await file.read()).decode("utf-8", errors="ignore")
        source = file.filename
    elif text:
        content = text
    else:
        raise HTTPException(400, "Provide a file or text body")

    conn = get_conn()
    try:
        count = ingest(conn, content, {"source": source})
    finally:
        conn.close()
    return {"chunks_ingested": count, "source": source}


@app.post("/ingest/sample")
async def ingest_sample():
    if not SAMPLE_DOC.exists():
        raise HTTPException(404, "Sample document not found in docs/")
    content = SAMPLE_DOC.read_text()
    conn = get_conn()
    try:
        count = ingest(conn, content, {"source": SAMPLE_DOC.name})
    finally:
        conn.close()
    return {"chunks_ingested": count, "source": SAMPLE_DOC.name}


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
async def query_endpoint(req: QueryRequest):
    conn = get_conn()
    try:
        result = answer(conn, req.question)
    except Exception as exc:
        raise HTTPException(500, str(exc))
    finally:
        conn.close()
    return {"answer": result, "question": req.question}


@app.get("/stats")
async def stats():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            count = cur.fetchone()[0]
    finally:
        conn.close()
    return {"document_chunks": count}
