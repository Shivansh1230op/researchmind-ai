"""Document loading and text extraction service.

Supports PDF, DOCX, and TXT files.  Extracts text along with page-level
metadata so that source citations can reference specific pages.

Key design decisions:
- PDFs use PyMuPDF (fitz) which handles large/malformed PDFs better than
  alternatives and gives page-level text extraction.
- DOCX uses python-docx to extract paragraph text.
- TXT files are read directly with encoding detection fallback.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DocumentLoader:
    """Load and extract text from uploaded documents.

    Each loader method returns a list of ``(page_number, text)`` tuples so
    the caller can preserve page information for citations.
    """

    def __init__(self) -> None:
        self.supported_extensions = {".pdf", ".docx", ".txt", ".md"}

    def load_document(
        self, file_path: str, file_type: Optional[str] = None
    ) -> Tuple[List[Tuple[int, str]], Dict[str, str]]:
        """Load a document and return page-level text plus metadata.

        Args:
            file_path: Path to the file on disk.
            file_type: Optional file type override (e.g. "pdf").

        Returns:
            A tuple of:
            - List of (page_number, text) pairs (page numbers start at 1).
            - Metadata dict with keys like 'author', 'title', 'num_pages'.

        Raises:
            ValueError: If the file type is not supported or the file is malformed.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine file type from extension if not provided
        if file_type is None:
            file_type = path.suffix.lower().lstrip(".")
        else:
            file_type = file_type.lower().lstrip(".")

        if f".{file_type}" not in self.supported_extensions:
            raise ValueError(
                f"Unsupported file type: .{file_type}. "
                f"Supported types: {self.supported_extensions}"
            )

        logger.info(f"Loading document: {path.name} (type={file_type})")

        if file_type == "pdf":
            pages, metadata = self._load_pdf(path)
        elif file_type == "docx":
            pages, metadata = self._load_docx(path)
        elif file_type in {"txt", "md"}:
            pages, metadata = self._load_txt(path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        logger.info(
            f"Loaded {path.name}: {len(pages)} pages, "
            f"{sum(len(t) for _, t in pages)} characters"
        )
        return pages, metadata

    def _load_pdf(self, file_path: Path) -> Tuple[List[Tuple[int, str]], Dict[str, str]]:
        """Extract text from a PDF file using PyMuPDF (fitz).

        PyMuPDF is robust against malformed PDFs and provides metadata
        such as author, title, and subject.
        """
        import fitz  # PyMuPDF

        pages: List[Tuple[int, str]] = []
        metadata: Dict[str, str] = {}

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            raise ValueError(f"Failed to open PDF (possibly malformed): {exc}") from exc

        try:
            # Extract document-level metadata
            pdf_meta = doc.metadata or {}
            metadata = {
                "title": pdf_meta.get("title", ""),
                "author": pdf_meta.get("author", ""),
                "subject": pdf_meta.get("subject", ""),
                "creator": pdf_meta.get("creator", ""),
                "num_pages": str(doc.page_count),
            }

            # Extract text per page
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text("text").strip()
                # Skip pages with no extractable text (e.g. scanned image pages)
                if text:
                    pages.append((page_num + 1, text))
                else:
                    # Still include a placeholder so page numbers are preserved
                    pages.append((page_num + 1, ""))

        finally:
            doc.close()

        return pages, metadata

    def _load_docx(self, file_path: Path) -> Tuple[List[Tuple[int, str]], Dict[str, str]]:
        """Extract text from a Word document using python-docx.

        DOCX files don't have natural "pages", so each paragraph is treated
        as a separate text block.  All paragraphs are combined into a
        single "page" (page 1) for citation purposes.
        """
        from docx import Document as DocxDocument

        try:
            doc = DocxDocument(str(file_path))
        except Exception as exc:
            raise ValueError(f"Failed to open DOCX file: {exc}") from exc

        # Extract metadata
        core_props = doc.core_properties
        metadata = {
            "title": core_props.title or "",
            "author": core_props.author or "",
            "subject": core_props.subject or "",
            "created": str(core_props.created) if core_props.created else "",
            "modified": str(core_props.modified) if core_props.modified else "",
        }

        # Extract paragraph text
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text = cell.text.strip()
                    if text:
                        paragraphs.append(text)

        full_text = "\n\n".join(paragraphs)
        metadata["num_pages"] = "1"

        # DOCX doesn't have pages, so everything is "page 1"
        return [(1, full_text)], metadata

    def _load_txt(self, file_path: Path) -> Tuple[List[Tuple[int, str]], Dict[str, str]]:
        """Read a plain text file with encoding detection fallback.

        Tries UTF-8 first, then falls back to latin-1 (which never fails).
        """
        encodings_to_try = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

        text = ""
        for encoding in encodings_to_try:
            try:
                text = file_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            # Last resort: read bytes and decode with errors='replace'
            raw_bytes = file_path.read_bytes()
            text = raw_bytes.decode("utf-8", errors="replace")

        metadata = {
            "title": file_path.stem,
            "author": "",
            "subject": "",
            "num_pages": "1",
        }

        # For TXT files, everything is "page 1"
        return [(1, text)], metadata

    def validate_file(self, file_path: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Validate that a file is acceptable for upload.

        Args:
            file_path: The original filename (for extension check).
            file_size: Size of the file in bytes.

        Returns:
            (True, None) if valid, (False, error_message) otherwise.
        """
        from app.core.config import get_settings

        settings = get_settings()

        # Check file extension
        ext = Path(file_path).suffix.lower()
        if ext not in self.supported_extensions:
            return False, (
                f"File type '{ext}' is not supported. "
                f"Allowed types: {', '.join(self.supported_extensions)}"
            )

        # Check file size
        if file_size > settings.max_file_size_bytes:
            return False, (
                f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds "
                f"maximum allowed size ({settings.max_file_size_mb} MB)"
            )

        if file_size == 0:
            return False, "File is empty"

        return True, None
