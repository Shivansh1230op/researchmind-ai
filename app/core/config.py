"""Application configuration loaded from environment variables.

All settings are read from the environment (or a local .env file) so that
no secrets are ever hardcoded.  The Settings object is created once at
import time and re-used throughout the application via the ``get_settings``
function, which implements a simple caching pattern.
"""

from functools import lru_cache
from typing import List
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for DocuMind AI.

    Attributes are populated from environment variables (case-insensitive)
    or from a ``.env`` file in the project root.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────
    app_name: str = "ResearchMind AI"
    auth_required: bool = True
    cookie_secure: bool = False
    processing_worker_enabled: bool = True
    preload_embeddings: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_starttls: bool = True
    smtp_use_ssl: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2:3b"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # ── OpenAI ────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key for LLM access")
    openai_base_url: str = Field(default="", description="Custom OpenAI-compatible API base URL (e.g. OpenRouter)")
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 2048

    # ── Embeddings ────────────────────────────────────────────────
    # Use a local Sentence Transformers model so embeddings work offline
    # and do not consume OpenAI quota.
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    embedding_cpu_threads: int = Field(default=4, ge=1, le=32)

    # ── Vector Store (ChromaDB) ──────────────────────────────────
    chroma_persist_dir: str = "data/chroma_db"
    chroma_collection_name: str = "documind_collection"

    # ── Text Processing ──────────────────────────────────────────
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_file_size_mb: int = 50
    allowed_file_types: str = "pdf,docx,txt,md"

    # ── Retrieval ────────────────────────────────────────────────
    default_top_k: int = 5
    similarity_threshold: float = 0.3
    enable_reranking: bool = True
    enable_hybrid_search: bool = True
    bm25_weight: float = 0.3
    vector_weight: float = 0.7

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite:///data/documind.db"

    # ── Rate Limiting ────────────────────────────────────────────
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # ── File Paths ───────────────────────────────────────────────
    upload_dir: str = "data/uploads"
    sample_docs_dir: str = "data/sample_documents"

    # ── Conversation Memory ──────────────────────────────────────
    max_conversation_history: int = 10

    # ── LLM Backend Selection ───────────────────────────────────
    # When set to "local", use a HuggingFace pipeline instead of OpenAI.
    llm_backend: str = "openai"
    local_model_name: str = "mistralai/Mistral-7B-Instruct-v0.2"

    # ── Derived helpers ──────────────────────────────────────────
    @computed_field  # type: ignore[misc]
    @property
    def allowed_extensions(self) -> List[str]:
        """Return allowed file extensions as a clean list."""
        return [ext.strip().lower() for ext in self.allowed_file_types.split(",")]

    @computed_field  # type: ignore[misc]
    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB limit to bytes."""
        return self.max_file_size_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        """Create data directories if they don't exist."""
        # Extract the directory path from the database URL.
        # For SQLite: "sqlite:///data/documind.db" → "data"
        directories = [
            self.upload_dir,
            self.chroma_persist_dir,
            self.sample_docs_dir,
        ]
        if self.database_url.startswith("sqlite:///"):
            directories.append(Path(self.database_url[len("sqlite:///"):]).parent)
        for dir_path in directories:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Using ``lru_cache`` means the ``.env`` file is read only once and the
    same object is reused everywhere, which is both faster and guarantees
    a single source of truth.
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
