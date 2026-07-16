"""Central configuration for the RAG service. All values come from env vars."""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Vertex AI (Gemini) — auth via ADC, no API key
    embedding_model: str = "text-embedding-005"
    embedding_dim: int = 768
    chat_model: str = "gemini-2.5-flash"
    vertex_location: str = "us-central1"

    # Cloud SQL (Postgres + pgvector). Use the Cloud SQL Auth Proxy socket in prod.
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "finops_rag"
    db_user: str = "raguser"
    db_password: str = ""
    # e.g. "/cloudsql/project:region:instance" — takes precedence over host/port
    db_unix_socket: str = ""

    # Cloud Storage
    gcs_bucket: str = "finops-agent-docs"
    gcp_project: str = ""

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Retrieval
    top_k: int = 6
    fetch_k: int = 24  # candidates fetched before reranking
    mmr_lambda: float = 0.6

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
