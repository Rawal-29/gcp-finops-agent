"""FastAPI service (Cloud Run). Serves:
  - RAG:       POST /query, POST /ingest
  - Dashboard: GET /anomalies, GET /agent/runs, GET /evals
"""
from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from rag.config import get_settings
from rag.retriever import Retriever

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@lru_cache
def get_retriever() -> Retriever:
    return Retriever()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_retriever().store.init_schema()
    yield


# ---------- auth ----------
# All routes except /health require X-API-Key matching the API_AUTH_KEY env var.
# When API_AUTH_KEY is unset (local dev, CI eval runner) auth is disabled.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Depends(_api_key_header)) -> None:
    expected = os.environ.get("API_AUTH_KEY", "")
    if not expected:
        return
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


app = FastAPI(title="FinOps Intelligence API", version="1.0.0", lifespan=lifespan)
# Everything except /health (probes can't send headers) sits behind the key.
protected = APIRouter(dependencies=[Depends(require_api_key)])

# Browser traffic goes through the Next.js same-origin proxy, so no origins are
# needed by default; set CORS_ORIGINS only for direct cross-origin access.
_cors_origins = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["X-API-Key", "Content-Type"],
    )


# ---------- schemas ----------
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int | None = Field(None, ge=1, le=20)
    generate: bool = True  # False -> retrieval only (used by evals)


class ChunkOut(BaseModel):
    content: str
    source: str
    score: float
    chunk_index: int


class QueryResponse(BaseModel):
    answer: str | None
    contexts: list[ChunkOut]


class IngestRequest(BaseModel):
    prefix: str = ""


# ---------- RAG endpoints ----------
@protected.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    r = get_retriever()
    try:
        if req.generate:
            result = r.answer(req.question, req.top_k)
            return QueryResponse(**result)
        chunks = r.retrieve(req.question, req.top_k)
        return QueryResponse(answer=None, contexts=[ChunkOut(**c.to_dict()) for c in chunks])
    except Exception as exc:  # surface as 502, never 500 stack traces
        log.exception("query failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@protected.post("/ingest", status_code=202)
def ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
    from rag.ingest import ingest_bucket

    background.add_task(ingest_bucket, req.prefix)
    return {"status": "accepted", "prefix": req.prefix}


# ---------- dashboard endpoints ----------
@protected.get("/anomalies")
def anomalies(limit: int = Query(50, le=200)) -> list[dict]:
    """Recent billing anomalies from BigQuery."""
    from google.cloud import bigquery

    s = get_settings()
    client = bigquery.Client(project=s.gcp_project or None)
    sql = f"""
        SELECT detected_at, project_id, service, resource_name,
               baseline_cost, current_cost,
               ROUND(SAFE_DIVIDE(current_cost - baseline_cost, baseline_cost) * 100, 1) AS spike_pct,
               status
        FROM `{s.gcp_project}.finops.anomalies`
        ORDER BY detected_at DESC
        LIMIT {int(limit)}
    """
    return [dict(row) for row in client.query(sql).result()]


@protected.get("/agent/runs")
def agent_runs(limit: int = Query(25, le=100)) -> list[dict]:
    """Agent run history from Firestore."""
    from google.cloud import firestore

    db = firestore.Client()
    docs = (
        db.collection("agent_runs")
        .order_by("started_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


@protected.get("/evals")
def evals(limit: int = Query(100, le=500)) -> list[dict]:
    """RAGAS eval history from BigQuery."""
    from google.cloud import bigquery

    s = get_settings()
    client = bigquery.Client(project=s.gcp_project or None)
    sql = f"""
        SELECT run_at, git_sha, faithfulness, answer_relevancy, context_recall, passed
        FROM `{s.gcp_project}.finops.eval_results`
        ORDER BY run_at DESC
        LIMIT {int(limit)}
    """
    return [dict(row) for row in client.query(sql).result()]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "chunks": get_retriever().store.count()}


app.include_router(protected)
