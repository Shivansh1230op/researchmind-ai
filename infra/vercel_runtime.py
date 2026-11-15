"""Configure cloud-only adapters before any application module is imported."""
import os


def configure():
    defaults = {
        "STORAGE_BACKEND": "vercel_blob", "VECTOR_BACKEND": "postgres",
        "PROCESSING_BACKEND": "vercel_queue", "EMBEDDING_BACKEND": "gemini",
        "PROCESSING_WORKER_ENABLED": "false", "PRELOAD_EMBEDDINGS": "false",
        "ENABLE_RERANKING": "false", "COOKIE_SECURE": "true", "AUTH_REQUIRED": "true",
        "UPLOAD_DIR": "/tmp/researchmind/uploads", "CHROMA_PERSIST_DIR": "/tmp/researchmind/chroma",
        "SAMPLE_DOCS_DIR": "/tmp/researchmind/samples", "DEBUG": "false",
    }
    for name, value in defaults.items():
        os.environ.setdefault(name, value)
    database = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL", "")
    if not database.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("Connect PostgreSQL storage to the Vercel project and set DATABASE_URL.")
    os.environ["DATABASE_URL"] = database
    origins = [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL"):
        if os.environ.get(name):
            origins.append("https://" + os.environ[name])
    if os.environ.get("PUBLIC_URL"):
        origins.append(os.environ["PUBLIC_URL"].rstrip("/"))
    os.environ["CORS_ORIGINS"] = ",".join(dict.fromkeys(origins))
