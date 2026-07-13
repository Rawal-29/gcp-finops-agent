"""pgvector CRUD on Cloud SQL Postgres.

Schema: one `documents` table with an ivfflat index on the embedding column.
Uses a small connection pool; safe for Cloud Run concurrency.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool

from rag.config import get_settings

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,           -- gs:// URI of source doc
    chunk_index INT  NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}'::jsonb,
    embedding   vector(%(dim)s) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, chunk_index)
);

CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""


class VectorStore:
    def __init__(self) -> None:
        s = get_settings()
        dsn: dict[str, Any] = {
            "dbname": s.db_name,
            "user": s.db_user,
            "password": s.db_password,
        }
        if s.db_unix_socket:
            dsn["host"] = s.db_unix_socket  # Cloud SQL Auth Proxy socket dir
        else:
            dsn["host"], dsn["port"] = s.db_host, s.db_port
        self._pool = ThreadedConnectionPool(minconn=1, maxconn=8, **dsn)
        self._dim = s.embedding_dim

    @contextmanager
    def _conn(self) -> Iterator[Any]:
        conn = self._pool.getconn()
        try:
            register_vector(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def init_schema(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(_SCHEMA % {"dim": self._dim})
        log.info("schema ready (dim=%s)", self._dim)

    def upsert_chunks(
        self,
        source: str,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadata: dict | None = None,
    ) -> int:
        """Idempotent: re-ingesting a source replaces its chunks."""
        assert len(chunks) == len(embeddings)
        meta = json.dumps(metadata or {})
        rows = [(source, i, c, meta, list(e)) for i, (c, e) in enumerate(zip(chunks, embeddings))]
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE source = %s", (source,))
            execute_values(
                cur,
                "INSERT INTO documents (source, chunk_index, content, metadata, embedding) VALUES %s",
                rows,
                template="(%s, %s, %s, %s, %s::vector)",
            )
        log.info("upserted %d chunks for %s", len(rows), source)
        return len(rows)

    def similarity_search(
        self, embedding: Sequence[float], k: int, min_score: float = 0.0
    ) -> list[dict]:
        """Cosine similarity search. Returns content, metadata, score, embedding."""
        with self._conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, source, chunk_index, content, metadata,
                       embedding,
                       1 - (embedding <=> %s::vector) AS score
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (list(embedding), list(embedding), k),
            )
            rows = [dict(r) for r in cur.fetchall()]
        return [r for r in rows if r["score"] >= min_score]

    def count(self) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM documents")
            return cur.fetchone()[0]

    def delete_source(self, source: str) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE source = %s", (source,))
            return cur.rowcount
