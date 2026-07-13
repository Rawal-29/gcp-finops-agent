"""Call the Phase 1 RAG service. Uses ID-token auth for private Cloud Run."""
from __future__ import annotations

import logging
import os

import google.auth.transport.requests
import google.oauth2.id_token
import requests

log = logging.getLogger(__name__)

RAG_API_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")
TIMEOUT = 60


def _auth_headers() -> dict:
    """Cloud Run service-to-service auth. No-op for localhost."""
    if "localhost" in RAG_API_URL or "127.0.0.1" in RAG_API_URL:
        return {}
    auth_req = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(auth_req, RAG_API_URL)
    return {"Authorization": f"Bearer {token}"}


def query_rag(question: str, top_k: int = 6) -> dict:
    """Returns {answer, contexts}. Raises on HTTP error so graph can retry."""
    resp = requests.post(
        f"{RAG_API_URL}/query",
        json={"question": question, "top_k": top_k, "generate": True},
        headers=_auth_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    log.info("rag query ok: %d contexts", len(data.get("contexts", [])))
    return data
