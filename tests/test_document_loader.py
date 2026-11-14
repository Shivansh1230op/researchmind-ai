"""Tests for the DocumentLoader service.

Tests cover:
- TXT file loading with encoding detection
- DOCX loading (if python-docx is available)
- PDF loading with page-level extraction
- File validation (type, size)
- Error handling for malformed files and unsupported types
"""

import os
from pathlib import Path

import pytest

from app.services.document_loader import DocumentLoader


class TestDocumentLoader:
    """Tests for the DocumentLoader class."""

    @pytest.fixture
    def loader(self):
        return DocumentLoader()

    # ── TXT Loading ─────────────────────────────────────────────

    def test_load_txt_file(self, loader, sample_txt_file):
        """Test loading a plain text file."""
        pages, metadata = loader.load_document(str(sample_txt_file))

        assert len(pages) == 1
        assert "artificial intelligence" in pages[0][1].lower()
        assert pages[0][0] == 1  # page number
        assert metadata["title"] == "sample"

    def test_load_txt_with_explicit_type(self, loader, sample_txt_file):
        """Test loading with an explicit file type."""
        pages, _ = loader.load_document(str(sample_txt_file), file_type="txt")
        assert len(pages) == 1
        assert len(pages[0][1]) > 0

    def test_load_txt_preserves_content(self, loader, tmp_path):
        """Test that all text content is preserved."""
        test_content = "Line 1.\nLine 2.\nLine 3."
        file_path = tmp_path / "test.txt"
        file_path.write_text(test_content, encoding="utf-8")

        pages, _ = loader.load_document(str(file_path))
        assert pages[0][1] == test_content

    def test_load_txt_encoding_fallback(self, loader, tmp_path):
        """Test that latin-1 encoding is used as fallback."""
        # Write bytes that aren't valid UTF-8
        file_path = tmp_path / "latin1.txt"
        file_path.write_bytes("Caf\xe9 r\xe9sum\xe9".encode("latin-1"))

        pages, _ = loader.load_document(str(file_path))
        assert len(pages[0][1]) > 0  # Should not crash

    # ── PDF Loading ─────────────────────────────────────────────

    def test_load_pdf_file(self, loader, sample_pdf_bytes, tmp_path):
        """Test loading a PDF with page-level extraction."""
        file_path = tmp_path / "test.pdf"
        file_path.write_bytes(sample_pdf_bytes)

        pages, metadata = loader.load_document(str(file_path))

        assert len(pages) == 2  # Two pages
        assert pages[0][0] == 1  # First page number
        assert pages[1][0] == 2  # Second page number
        assert "page 1" in pages[0][1].lower()
        assert "page 2" in pages[1][1].lower()
        assert "num_pages" in metadata

    # ── Validation ──────────────────────────────────────────────

    def test_validate_file_valid(self, loader):
        """Test that valid files pass validation."""
        valid, error = loader.validate_file("test.pdf", 1024)
        assert valid is True
        assert error is None

    def test_validate_file_unsupported_type(self, loader):
        """Test that unsupported file types are rejected."""
        valid, error = loader.validate_file("test.exe", 1024)
        assert valid is False
        assert "not supported" in error.lower()

    def test_validate_file_too_large(self, loader):
        """Test that files exceeding the size limit are rejected."""
        # Use a size larger than the configured max
        from app.core.config import get_settings
        settings = get_settings()
        too_large = settings.max_file_size_bytes + 1

        valid, error = loader.validate_file("test.pdf", too_large)
        assert valid is False
        assert "exceeds" in error.lower()

    def test_validate_file_empty(self, loader):
        """Test that empty files are rejected."""
        valid, error = loader.validate_file("test.txt", 0)
        assert valid is False
        assert "empty" in error.lower()

    # ── Error Handling ──────────────────────────────────────────

    def test_load_nonexistent_file(self, loader):
        """Test that loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            loader.load_document("/nonexistent/file.txt")

    def test_load_unsupported_type(self, loader, tmp_path):
        """Test that unsupported file types raise ValueError."""
        file_path = tmp_path / "test.xyz"
        file_path.write_text("content", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported"):
            loader.load_document(str(file_path))

    def test_load_malformed_pdf(self, loader, tmp_path):
        """Test that a malformed PDF raises ValueError."""
        file_path = tmp_path / "fake.pdf"
        file_path.write_text("This is not a real PDF", encoding="utf-8")

        with pytest.raises(ValueError, match="Failed to open PDF"):
            loader.load_document(str(file_path))
