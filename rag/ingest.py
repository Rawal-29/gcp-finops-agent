"""Ingest pipeline: Cloud Storage PDFs -> chunks -> embeddings -> pgvector.

Run locally:  python -m rag.ingest --prefix pricing/
Runs in Cloud Run job or on demand via POST /ingest.
"""
from __future__ import annotations

import argparse
import io
import logging
import re

from google.cloud import storage
from pypdf import PdfReader

from rag.config import get_settings
from rag.llm import embed_texts
from rag.vector_store import VectorStore

log = logging.getLogger(__name__)

def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages)
    return re.sub(r"[ \t]+", " ", text)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Paragraph-aware sliding window. Prefers splitting on blank lines,
    falls back to sentence boundaries, then hard cuts."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 1 <= chunk_size:
            buf = f"{buf}\n{para}".strip()
            continue
        if buf:
            chunks.append(buf)
        # paragraph itself too big -> hard split with overlap
        while len(para) > chunk_size:
            cut = para.rfind(". ", 0, chunk_size)
            cut = cut + 1 if cut > chunk_size // 2 else chunk_size
            chunks.append(para[:cut].strip())
            para = para[max(cut - overlap, 0):]
        buf = para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) > 50]  # drop noise fragments


def ingest_bucket(prefix: str = "") -> dict:
    """Ingest every PDF under gs://<bucket>/<prefix>. Returns summary stats."""
    s = get_settings()
    gcs = storage.Client(project=s.gcp_project or None)
    bucket = gcs.bucket(s.gcs_bucket)
    store = VectorStore()
    store.init_schema()

    stats = {"files": 0, "chunks": 0, "skipped": []}
    for blob in bucket.list_blobs(prefix=prefix):
        if not blob.name.lower().endswith(".pdf"):
            continue
        uri = f"gs://{s.gcs_bucket}/{blob.name}"
        try:
            text = extract_pdf_text(blob.download_as_bytes())
            chunks = chunk_text(text, s.chunk_size, s.chunk_overlap)
            if not chunks:
                stats["skipped"].append(uri)
                continue
            embeddings = embed_texts(chunks)
            n = store.upsert_chunks(uri, chunks, embeddings, metadata={"filename": blob.name})
            stats["files"] += 1
            stats["chunks"] += n
            log.info("ingested %s (%d chunks)", uri, n)
        except Exception:
            log.exception("failed to ingest %s", uri)
            stats["skipped"].append(uri)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="", help="GCS prefix to ingest")
    args = parser.parse_args()
    print(ingest_bucket(args.prefix))
