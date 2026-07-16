"""Retrieval: embed query -> pgvector similarity -> MMR rerank.

MMR (maximal marginal relevance) trades relevance vs diversity so the agent
gets non-duplicate context, which matters a lot with chunked pricing docs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from rag.config import get_settings
from rag.vector_store import VectorStore

log = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float
    chunk_index: int

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "source": self.source,
            "score": round(self.score, 4),
            "chunk_index": self.chunk_index,
        }


def _mmr(
    query_vec: np.ndarray,
    candidates: list[dict],
    k: int,
    lam: float,
) -> list[dict]:
    """Greedy MMR over candidate rows (each row carries its embedding)."""
    if len(candidates) <= k:
        return candidates
    embs = np.array([np.asarray(c["embedding"], dtype=np.float32) for c in candidates])
    embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    rel = embs @ q

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < k:
        if not selected:
            best = int(np.argmax(rel[remaining]))
            selected.append(remaining.pop(best))
            continue
        sim_to_sel = embs[remaining] @ embs[selected].T  # (n_rem, n_sel)
        mmr_score = lam * rel[remaining] - (1 - lam) * sim_to_sel.max(axis=1)
        best = int(np.argmax(mmr_score))
        selected.append(remaining.pop(best))
    return [candidates[i] for i in selected]


class Retriever:
    def __init__(self, store: VectorStore | None = None) -> None:
        self.settings = get_settings()
        self.store = store or VectorStore()

    def embed_query(self, query: str) -> list[float]:
        from rag.llm import embed_texts

        return embed_texts([query], for_query=True)[0]

    def retrieve(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        s = self.settings
        k = k or s.top_k
        qvec = self.embed_query(query)
        candidates = self.store.similarity_search(qvec, k=s.fetch_k)
        reranked = _mmr(np.asarray(qvec, dtype=np.float32), candidates, k, s.mmr_lambda)
        log.info("query=%r fetched=%d returned=%d", query[:80], len(candidates), len(reranked))
        return [
            RetrievedChunk(
                content=r["content"],
                source=r["source"],
                score=float(r["score"]),
                chunk_index=r["chunk_index"],
            )
            for r in reranked
        ]

    def answer(self, query: str, k: int | None = None) -> dict:
        """RAG answer: retrieve context then ground the Gemini response in it."""
        chunks = self.retrieve(query, k)
        context = "\n\n---\n\n".join(
            f"[{i + 1}] (source: {c.source})\n{c.content}" for i, c in enumerate(chunks)
        )
        from rag.llm import generate

        answer = generate(
            f"Context:\n{context}\n\nQuestion: {query}",
            system=(
                "You are a GCP FinOps expert. Answer ONLY from the provided "
                "context. Cite chunk numbers like [1]. If the context is "
                "insufficient, say so explicitly — do not guess prices."
            ),
        )
        return {"answer": answer, "contexts": [c.to_dict() for c in chunks]}
