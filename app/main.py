"""FastAPI application entry point for DocuMind AI.

This module creates and configures the FastAPI application:
- CORS middleware for cross-origin frontend requests
- Rate limiting middleware
- Startup/shutdown event handlers
- Exception handlers for graceful error responses
- Swagger/OpenAPI documentation configuration
- Router inclusion for all API endpoints

Run with: ``uvicorn app.main:app --reload``
"""

import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.api.routes import router
from app.api.workspace import router as workspace_router
from app.api.stream import router as stream_router
from app.api.signup import router as signup_router
from app.api.cloud_uploads import router as cloud_uploads_router
from app.api.queue_internal import router as queue_internal_router
from app.database.database import init_db

logger = get_logger(__name__)
settings = get_settings()


# ── Rate Limiter ──────────────────────────────────────────────
class RateLimiter:
    """Simple in-memory rate limiter using a sliding window.

    Tracks requests per client IP.  For production use, replace with
    a Redis-backed implementation.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict = defaultdict(deque)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        req_times = self._requests[client_id]

        # Remove timestamps outside the window
        while req_times and req_times[0] <= now - self.window:
            req_times.popleft()

        if len(req_times) >= self.max_requests:
            return False

        req_times.append(now)
        return True


_rate_limiter = RateLimiter(
    settings.rate_limit_requests,
    settings.rate_limit_window_seconds,
)


# ── Lifespan handler (replaces deprecated on_event) ───────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs on startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"LLM backend: {settings.llm_backend}")
    logger.info(f"Embedding model: {settings.embedding_model_name}")

    # Initialize database tables
    init_db()
    from app.services.processing_jobs import ProcessingWorker
    worker = ProcessingWorker() if settings.processing_worker_enabled else None
    if worker:
        worker.start()

    logger.info("Application started successfully")
    try:
        yield
    finally:
        if worker:
            worker.stop()

    # Shutdown
    logger.info("Shutting down DocuMind AI")


# ── Create the FastAPI application ────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "DocuMind AI is a RAG-powered document intelligence platform. "
        "Upload PDFs, Word docs, and text files, then ask natural-language "
        "questions and get answers grounded in your documents with source citations."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────

# Allow authenticated requests from the configured website origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),  # In production, restrict to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware applied to all requests."""
    client_id = request.client.host if request.client else "unknown"

    if not _rate_limiter.is_allowed(client_id):
        logger.warning(f"Rate limit exceeded for {client_id}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Rate limit exceeded. Please slow down.",
                "error_code": "RATE_LIMIT_EXCEEDED",
            },
        )

    # Add timing header
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Log all incoming requests with method, path, and duration."""
    response = await call_next(request)
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code}",
        extra={
            "method": request.method,
            "path": str(request.url.path),
            "status": response.status_code,
        },
    )
    return response


# ── Exception Handlers ────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred.",
            "error_code": "INTERNAL_ERROR",
        },
    )


# ── Include API Routes ────────────────────────────────────────
app.include_router(router, tags=["ResearchMind API"])
app.include_router(workspace_router, tags=["Workspace API"])
app.include_router(stream_router, tags=["Streaming API"])
app.include_router(signup_router, tags=["Signup verification"])
app.include_router(cloud_uploads_router, tags=["Cloud uploads"])
app.include_router(queue_internal_router)
app.include_router(signup_router, prefix="/api/v1", include_in_schema=False)
if settings.processing_backend == "vercel_queue":
    app.include_router(cloud_uploads_router, prefix="/api", include_in_schema=False)
    # Service routing preserves /api, unlike the development Next.js proxy.
    app.include_router(signup_router, prefix="/api", include_in_schema=False)
    app.include_router(stream_router, prefix="/api", include_in_schema=False)
    app.include_router(router, prefix="/api", include_in_schema=False)
    app.include_router(workspace_router, prefix="/api", include_in_schema=False)
app.include_router(stream_router, prefix="/api/v1", include_in_schema=False)
app.include_router(router, prefix="/api/v1", include_in_schema=False)
app.include_router(workspace_router, prefix="/api/v1", include_in_schema=False)


@app.get("/ready", tags=["Health"])
def ready():
    """Readiness without loading AI models or making provider calls."""
    from sqlalchemy import text
    from app.database.database import engine
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}


if settings.processing_backend == "vercel_queue":
    app.add_api_route("/api/ready", ready, methods=["GET"], include_in_schema=False)

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with basic API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


# ── Custom OpenAPI schema (adds tags grouping in Swagger) ─────
def custom_openapi():
    """Generate a custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
