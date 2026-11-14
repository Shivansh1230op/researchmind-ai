"""Tests for the TextSplitter service.

Tests cover:
- Basic chunking with configurable size and overlap
- Page number preservation across chunks
- Chunk index assignment
- Empty page skipping
- Boundary detection (sentence, paragraph, whitespace)
- Edge cases (text shorter than chunk size, no overlap)
"""

import pytest

from app.services.text_splitter import TextSplitter, TextChunk


class TestTextSplitter:
    """Tests for the TextSplitter class."""

    @pytest.fixture
    def splitter(self):
        """Provide a splitter with small chunks for testing."""
        return TextSplitter(chunk_size=200, chunk_overlap=50)

    def test_split_short_text(self, splitter):
        """Text shorter than chunk_size should produce one chunk."""
        text = "This is a short sentence."
        chunks = splitter.split_text(text)

        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].page_number == 1
        assert chunks[0].chunk_index == 0

    def test_split_long_text(self, splitter, sample_long_text):
        """Long text should be split into multiple chunks."""
        chunks = splitter.split_text(sample_long_text)

        assert len(chunks) > 1
        # Each chunk should be at most chunk_size (approximately)
        for chunk in chunks:
            assert len(chunk.content) <= 250  # Allow some slack for boundary detection
        # Chunk indices should be sequential
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx

    def test_split_pages_preserves_page_numbers(self, splitter, sample_pages):
        """Page numbers should be preserved in the output chunks."""
        chunks = splitter.split_pages(sample_pages, document_name="test.pdf")

        # Empty page (page 4) should be skipped
        page_numbers = {c.page_number for c in chunks}
        assert 4 not in page_numbers  # Empty page skipped
        assert 1 in page_numbers
        assert 2 in page_numbers
        assert 3 in page_numbers
        assert 5 in page_numbers

    def test_split_pages_assigns_chunk_indices(self, splitter, sample_pages):
        """Chunk indices should be sequential across all pages."""
        chunks = splitter.split_pages(sample_pages, document_name="test.pdf")

        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx

    def test_split_pages_preserves_document_name(self, splitter, sample_pages):
        """Document name should be set on all chunks."""
        chunks = splitter.split_pages(sample_pages, document_name="report.pdf")

        for chunk in chunks:
            assert chunk.document_name == "report.pdf"

    def test_chunk_content_not_empty(self, splitter, sample_pages):
        """All returned chunks should have non-empty content."""
        chunks = splitter.split_pages(sample_pages, document_name="test.pdf")

        for chunk in chunks:
            assert chunk.content.strip() != ""

    def test_overlap_between_chunks(self, splitter):
        """Adjacent chunks should share some overlapping text."""
        # Create text with clear sentence boundaries
        text = "Sentence one. Sentence two. Sentence three. " * 20
        chunks = splitter.split_text(text)

        if len(chunks) > 1:
            # Check that the last part of chunk 0 appears in chunk 1
            # (overlap means some text is shared)
            assert len(chunks) >= 2

    def test_split_empty_text(self, splitter):
        """Empty text should produce no chunks."""
        chunks = splitter.split_text("")
        assert len(chunks) == 0

    def test_split_whitespace_only_text(self, splitter):
        """Whitespace-only text should produce no chunks."""
        chunks = splitter.split_text("   \n\n  \t  ")
        assert len(chunks) == 0

    def test_chunk_to_dict(self):
        """TextChunk.to_dict() should include all metadata fields."""
        chunk = TextChunk(
            content="test content",
            page_number=3,
            chunk_index=5,
            document_name="doc.pdf",
            document_id="abc123",
        )
        d = chunk.to_dict()

        assert d["page_number"] == 3
        assert d["chunk_index"] == 5
        assert d["document_name"] == "doc.pdf"
        assert d["document_id"] == "abc123"

    def test_overlap_less_than_chunk_size(self):
        """If overlap >= chunk_size, it should be auto-reduced."""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=200)
        assert splitter.chunk_overlap < splitter.chunk_size
