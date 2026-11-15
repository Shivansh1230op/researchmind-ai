"""Vercel FastAPI service entrypoint."""
from infra.vercel_runtime import configure

configure()

from app.main import app  # noqa: E402,F401
