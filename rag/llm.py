"""Vertex AI (Gemini) helpers shared by the RAG service and the agent.

Auth is Application Default Credentials — service accounts on GCP, your
gcloud ADC locally. No API keys anywhere.
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import EmbedContentConfig, GenerateContentConfig

from rag.config import get_settings

log = logging.getLogger(__name__)


def _with_retry(fn, attempts: int = 4):
    """Retry 429/503 with exponential backoff — Vertex dynamic shared quota
    throttles bursts even at low volume."""
    for i in range(attempts):
        try:
            return fn()
        except genai_errors.APIError as exc:
            if exc.code not in (429, 503) or i == attempts - 1:
                raise
            wait = 2 ** (i + 2)  # 4s, 8s, 16s
            log.warning("Vertex %s, retrying in %ss", exc.code, wait)
            time.sleep(wait)


@lru_cache
def client() -> genai.Client:
    s = get_settings()
    return genai.Client(
        vertexai=True,
        project=s.gcp_project or None,
        location=s.vertex_location,
    )


def embed_texts(texts: list[str], *, for_query: bool = False) -> list[list[float]]:
    """Embed with the task type matched to use: documents at ingest, queries at
    retrieval. Vertex caps requests at 250 inputs; we batch below that."""
    s = get_settings()
    task = "RETRIEVAL_QUERY" if for_query else "RETRIEVAL_DOCUMENT"
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        resp = _with_retry(lambda: client().models.embed_content(
            model=s.embedding_model,
            contents=batch,
            config=EmbedContentConfig(task_type=task, output_dimensionality=s.embedding_dim),
        ))
        out.extend(e.values for e in resp.embeddings)
    return out


def generate(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.1,
    response_schema: dict | None = None,
) -> str:
    """Single-turn generation. Pass response_schema to force valid JSON out."""
    s = get_settings()
    config = GenerateContentConfig(
        temperature=temperature,
        system_instruction=system,
        response_mime_type="application/json" if response_schema else None,
        response_schema=response_schema,
    )
    resp = _with_retry(lambda: client().models.generate_content(
        model=s.chat_model, contents=prompt, config=config
    ))
    return resp.text or ""
