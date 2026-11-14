"""Pydantic schemas for request validation and response serialization.

These models are used by FastAPI for automatic request validation,
Swagger/OpenAPI documentation, and consistent JSON response shapes.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Document Schemas ─────────────────────────────────────────

class DocumentMetadata(BaseModel):
    """Metadata about a document returned to the client."""

    id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original file name")
    file_type: str = Field(..., description="File extension (pdf, docx, txt)")
    file_size: int = Field(..., description="File size in bytes")
    total_pages: Optional[int] = Field(None, description="Number of pages (if applicable)")
    total_chunks: int = Field(0, description="Number of text chunks")
    status: str = Field(..., description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    created_at: datetime = Field(..., description="Upload timestamp")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    processing_stage: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Response containing a list of all uploaded documents."""

    documents: List[DocumentMetadata] = Field(default_factory=list)
    total: int = Field(0, description="Total number of documents")


class DocumentDeleteResponse(BaseModel):
    """Response after deleting a document."""

    success: bool = Field(..., description="Whether deletion succeeded")
    message: str = Field(..., description="Human-readable result message")
    document_id: str = Field(..., description="ID of the deleted document")


# ── Chat Schemas ──────────────────────────────────────────────

class SourceCitation(BaseModel):
    """A single source citation for an AI answer."""

    document_id: str = Field(..., description="ID of the source document")
    document_name: str = Field(..., description="Name of the source document")
    page_number: Optional[int] = Field(None, description="Page number in the source document")
    chunk_index: int = Field(..., description="Index of the chunk within the document")
    content: str = Field(..., description="Excerpt from the source document")
    similarity_score: float = Field(..., description="Similarity score (0-1)")


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    question: str = Field(..., min_length=1, max_length=2000,
                          description="User's question")
    mode: Literal["quick", "deep", "simple", "critical", "summary", "compare"] = "quick"
    session_id: str = Field(..., description="Unique session identifier")
    document_ids: Optional[List[str]] = Field(
        None, description="Optional: restrict search to these documents only"
    )
    top_k: Optional[int] = Field(None, ge=1, le=20,
                                 description="Number of chunks to retrieve")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question cannot be blank")
        return v.strip()


class ChatResponse(BaseModel):
    """Response from the /chat endpoint."""

    answer: str = Field(..., description="AI-generated answer")
    sources: List[SourceCitation] = Field(default_factory=list,
                                          description="Source citations")
    session_id: str = Field(..., description="Session identifier")
    question: str = Field(..., description="The original question")
    confidence: float = Field(0.0, ge=0, le=1,
                               description="Confidence score (0-1)")
    no_answer_found: bool = Field(False, description="True if answer was not in documents")


# ── Chat History Schemas ──────────────────────────────────────

class ChatHistoryItem(BaseModel):
    """A single message in the chat history."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    sources: Optional[List[SourceCitation]] = Field(None, description="Sources for assistant messages")
    timestamp: datetime = Field(..., description="When the message was created")


class ChatHistoryResponse(BaseModel):
    """Response containing chat history for a session."""

    session_id: str = Field(..., description="Session identifier")
    messages: List[ChatHistoryItem] = Field(default_factory=list)
    total: int = Field(0, description="Total number of messages")


class ClearChatResponse(BaseModel):
    """Response after clearing chat history."""

    success: bool = Field(...)
    message: str = Field(...)
    session_id: str = Field(...)


# ── Summarization Schemas ─────────────────────────────────────

class SummarizeRequest(BaseModel):
    """Request body for document summarization."""

    document_id: str = Field(..., description="ID of the document to summarize")
    summary_type: str = Field(
        "comprehensive",
        description="Type of summary: 'comprehensive', 'key_points', 'definitions'"
    )
    length: Literal["short", "medium", "long"] = "medium"

    @field_validator("summary_type")
    @classmethod
    def validate_summary_type(cls, v: str) -> str:
        allowed = {"comprehensive", "key_points", "definitions", "short", "executive", "bullet_points", "academic", "chapters", "beginner"}
        if v not in allowed:
            raise ValueError(f"summary_type must be one of {allowed}")
        return v


class SummarizeResponse(BaseModel):
    """Response from the summarization endpoint."""

    document_id: str = Field(...)
    document_name: str = Field(...)
    summary: str = Field(..., description="Generated summary")
    summary_type: str = Field(...)
    key_points: Optional[List[str]] = Field(None, description="Key points if requested")
    definitions: Optional[List[Dict[str, str]]] = Field(None, description="Definitions if requested")
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False


class BatchSummarizeRequest(BaseModel):
    document_ids: List[str] = Field(min_length=1, max_length=10)
    summary_type: Literal["comprehensive", "key_points", "definitions", "short", "executive", "bullet_points", "academic", "chapters", "beginner"] = "comprehensive"
    length: Literal["short", "medium", "long"] = "medium"


# ── Document Comparison Schemas ──────────────────────────────

class CompareRequest(BaseModel):
    """Request body for comparing multiple documents."""

    document_ids: List[str] = Field(..., min_length=2, max_length=5,
                                     description="IDs of documents to compare")
    aspect: str = Field(
        "general",
        description="Aspect to compare: 'general', 'methodology', 'findings', 'arguments'"
    )


class CompareResponse(BaseModel):
    """Response from the comparison endpoint."""

    comparison: str = Field(..., description="Comparison analysis text")
    document_names: List[str] = Field(..., description="Names of compared documents")
    aspects_covered: List[str] = Field(default_factory=list)


# ── Health Schemas ────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field("healthy", description="Service health status")
    version: str = Field(..., description="Application version")
    database: str = Field(..., description="Database connection status")
    vector_store: str = Field(..., description="Vector store status")
    embedding_model: str = Field(..., description="Embedding model name")
    llm_backend: str = Field(..., description="Active LLM backend")


# ── Error Schemas ─────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response for all API errors."""

    detail: str = Field(..., description="Error description")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
