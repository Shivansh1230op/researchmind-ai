"""Shared pytest fixtures for the DocuMind AI test suite.

Provides fixtures for:
- A temporary test database (in-memory SQLite)
- A temporary ChromaDB collection
- Sample text documents
- A FastAPI test client
- Service instances wired up with test config
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Environment overrides for testing ──────────────────────────
# Use a temp directory so tests never touch real data
_TEST_DIR = tempfile.mkdtemp(prefix="documind_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR}/test.db"
os.environ["CHROMA_PERSIST_DIR"] = f"{_TEST_DIR}/chroma_db"
os.environ["UPLOAD_DIR"] = f"{_TEST_DIR}/uploads"
os.environ["SAMPLE_DOCS_DIR"] = f"{_TEST_DIR}/sample_docs"
os.environ["LLM_BACKEND"] = "openai"
os.environ["DEBUG"] = "false"
os.environ["AUTH_REQUIRED"] = "false"
os.environ["PROCESSING_WORKER_ENABLED"] = "false"
os.environ["PRELOAD_EMBEDDINGS"] = "false"
os.environ["RATE_LIMIT_REQUESTS"] = "10000"
os.environ["OPENAI_API_KEY"] = "test-key-not-real"

# Clear the settings cache so the new env vars take effect
from app.core.config import get_settings
get_settings.cache_clear()
settings = get_settings()

from app.database.database import engine, SessionLocal, Base, init_db
from app.database import models  # noqa: F401 — ensure models are registered


# ── Database fixtures ─────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables once at the start of the test session.

    This autouse fixture ensures tables exist before any test runs,
    even tests that don't explicitly depend on test_engine.
    """
    init_db()
    yield
    # Cleanup happens at session end via _TEST_DIR cleanup


@pytest.fixture
def db_session():
    """Provide a fresh database session for each test.

    Rolls back changes after each test to keep tests isolated.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ── Document fixtures ─────────────────────────────────────────

@pytest.fixture
def sample_txt_file() -> Path:
    """Create a sample TXT file for testing."""
    file_path = Path(_TEST_DIR) / "sample.txt"
    file_path.write_text(
        "This is a sample document about artificial intelligence. "
        "Artificial intelligence (AI) is the simulation of human intelligence "
        "by machines. AI includes machine learning, natural language processing, "
        "and computer vision. Machine learning is a subset of AI that enables "
        "systems to learn from data. Deep learning is a subset of machine learning "
        "that uses neural networks with many layers. "
        "Natural language processing (NLP) allows computers to understand human language. "
        "Computer vision enables machines to interpret visual information. "
        "AI has applications in healthcare, finance, transportation, and education.",
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def sample_long_text() -> str:
    """Return a long text string for chunking tests (~5000 chars)."""
    paragraph = (
        "Retrieval-Augmented Generation (RAG) combines retrieval and generation. "
        "RAG systems retrieve relevant documents and use them as context for an LLM. "
        "This approach reduces hallucination by grounding answers in source material. "
        "The retrieval component uses semantic search with embeddings. "
        "Embeddings are vector representations of text in high-dimensional space. "
        "Similar texts have similar embeddings, enabling similarity-based search. "
    )
    return " ".join([paragraph] * 25)  # ~5000+ chars


@pytest.fixture
def sample_pages():
    """Return sample page data as (page_number, text) tuples."""
    return [
        (1, "Page 1: Introduction to machine learning. ML is a subset of AI."),
        (2, "Page 2: Deep learning uses neural networks with many layers."),
        (3, "Page 3: NLP allows computers to understand human language."),
        (4, ""),  # Empty page (should be skipped)
        (5, "Page 5: Computer vision interprets visual information from images."),
    ]


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Create a simple PDF file in memory and return its bytes."""
    import fitz

    doc = fitz.open()  # New empty PDF
    page1 = doc.new_page()
    page1.insert_text((72, 72), "This is page 1. It discusses artificial intelligence.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "This is page 2. It covers machine learning basics.")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ── Service fixtures ──────────────────────────────────────────

@pytest.fixture
def embedding_service():
    """Provide an EmbeddingService instance for tests.

    NOTE: This will download the model on first run. Tests that don't
    need real embeddings should mock this fixture.
    """
    from app.services.embedding_service import EmbeddingService
    return EmbeddingService()


@pytest.fixture
def vector_store():
    """Provide a VectorStore instance with a test collection."""
    from app.services.vector_store import VectorStore
    vs = VectorStore(collection_name="test_collection")
    yield vs
    # Cleanup: delete the test collection
    try:
        vs.reset()
    except Exception:
        pass


@pytest.fixture
def text_splitter():
    """Provide a TextSplitter with small chunk size for tests."""
    from app.services.text_splitter import TextSplitter
    return TextSplitter(chunk_size=200, chunk_overlap=50)


@pytest.fixture
def chat_memory():
    """Provide a ChatMemoryService instance for tests."""
    from app.services.chat_memory import ChatMemoryService
    return ChatMemoryService()


# ── API client fixture ────────────────────────────────────────

@pytest.fixture(scope="session")
def api_client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient for API testing.

    The TestClient runs the full FastAPI app in-process, which means
    startup/shutdown events fire automatically.
    """
    from app.main import app
    with TestClient(app) as client:
        yield client


# ── Session-scoped cleanup ────────────────────────────────────

def pytest_sessionfinish(session, exitstatus):
    """Clean up the test directory after all tests complete."""
    try:
        shutil.rmtree(_TEST_DIR, ignore_errors=True)
    except Exception:
        pass
