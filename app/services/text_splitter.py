"""Text chunking service with configurable size and overlap.

Splits extracted document text into chunks suitable for embedding and
retrieval.  The splitter is page-aware: it preserves page numbers from
the document loader so that retrieved chunks can be cited with their
source page.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TextChunk:
    """A single chunk of text with its source metadata.

    Attributes:
        content: The text content of this chunk.
        page_number: Page number in the source document (1-indexed).
        chunk_index: Position of this chunk within the document (0-indexed).
        document_name: Name of the source document file.
        start_char: Starting character offset within the document.
        end_char: Ending character offset within the document.
    """

    content: str
    page_number: int
    chunk_index: int
    document_name: str = ""
    start_char: int = 0
    end_char: int = 0
    document_id: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for ChromaDB metadata storage."""
        return {
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "document_name": self.document_name,
            "document_id": self.document_id,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }


class TextSplitter:
    """Configurable text splitter that respects page boundaries.

    The splitter uses a sliding window approach:
    1. Iterate over pages from the document loader.
    2. Split each page's text into chunks of ``chunk_size`` characters
       with ``chunk_overlap`` characters of overlap.
    3. If a page's text is shorter than ``chunk_size``, the entire page
       becomes one chunk.
    4. Each chunk retains the page number for citation.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

        # Ensure overlap is smaller than chunk size
        if self.chunk_overlap >= self.chunk_size:
            logger.warning(
                f"chunk_overlap ({self.chunk_overlap}) >= chunk_size "
                f"({self.chunk_size}). Reducing overlap to {self.chunk_size // 4}."
            )
            self.chunk_overlap = self.chunk_size // 4

        logger.info(
            f"TextSplitter initialized: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )

    def split_pages(
        self,
        pages: List[tuple],
        document_name: str = "",
        document_id: str = "",
    ) -> List[TextChunk]:
        """Split page-level text into chunks.

        Args:
            pages: List of (page_number, text) tuples from DocumentLoader.
            document_name: Name of the source document.
            document_id: ID of the source document.

        Returns:
            List of TextChunk objects with page metadata preserved.
        """
        chunks: List[TextChunk] = []
        chunk_index = 0

        for page_number, page_text in pages:
            # Skip empty pages
            if not page_text or not page_text.strip():
                continue

            page_chunks = self._split_text(page_text)

            for chunk_text in page_chunks:
                chunk = TextChunk(
                    content=chunk_text.strip(),
                    page_number=page_number,
                    chunk_index=chunk_index,
                    document_name=document_name,
                    document_id=document_id,
                )
                chunks.append(chunk)
                chunk_index += 1

        logger.info(
            f"Split '{document_name}' into {len(chunks)} chunks "
            f"from {len(pages)} pages"
        )
        return chunks

    def split_text(
        self,
        text: str,
        document_name: str = "",
        document_id: str = "",
        page_number: int = 1,
    ) -> List[TextChunk]:
        """Split raw text (no page information) into chunks.

        Convenience method for plain text without page boundaries.
        All chunks will have ``page_number=1``.
        """
        page_chunks = self._split_text(text)
        chunks = []

        for idx, chunk_text in enumerate(page_chunks):
            chunk = TextChunk(
                content=chunk_text.strip(),
                page_number=page_number,
                chunk_index=idx,
                document_name=document_name,
                document_id=document_id,
            )
            chunks.append(chunk)

        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    def _split_text(self, text: str) -> List[str]:
        """Core splitting logic: sliding window over the text.

        Tries to split on sentence/paragraph boundaries when possible
        to avoid cutting mid-sentence.
        """
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            # Determine the end of this chunk
            end = start + self.chunk_size

            if end >= text_len:
                # Last chunk — take everything remaining
                chunks.append(text[start:])
                break

            # Try to find a good split point near the end of the chunk
            # (look for sentence boundaries or paragraph breaks)
            split_point = self._find_best_split_point(text, start, end)

            chunk_text = text[start:split_point]
            if chunk_text.strip():
                chunks.append(chunk_text)

            # Move start forward, accounting for overlap
            start = split_point - self.chunk_overlap
            if start < 0:
                start = 0

            # Prevent infinite loop if overlap is too large
            if split_point <= start:
                start = split_point

        return chunks

    def _find_best_split_point(self, text: str, start: int, end: int) -> int:
        """Find the best character position to split the chunk.

        Looks for sentence boundaries (.!?) followed by whitespace, or
        paragraph breaks (\\n\\n), within the last 20% of the chunk.
        Falls back to the hard end if no good boundary is found.
        """
        # Search window: last 20% of the chunk
        search_start = start + int(self.chunk_size * 0.8)
        search_end = end

        # Priority 1: paragraph break (double newline)
        for i in range(search_end, search_start, -1):
            if i < len(text) - 1 and text[i] == "\n" and text[i - 1] == "\n":
                return i + 1

        # Priority 2: sentence boundary (. ! ? followed by space or newline)
        for i in range(search_end, search_start, -1):
            if i < len(text) and text[i - 1] in ".!?" and (i >= len(text) or text[i] in " \n\t"):
                return i

        # Priority 3: any whitespace
        for i in range(search_end, search_start, -1):
            if i < len(text) and text[i] in " \t":
                return i + 1

        # No good boundary found — use the hard end
        return end
