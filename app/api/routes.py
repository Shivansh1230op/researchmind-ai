"""FastAPI route definitions for DocuMind AI.

All endpoints are defined on an ``APIRouter`` and included by the main
app.  Each route delegates to the appropriate service, keeping the route
handlers thin.

Endpoints:
    POST   /documents/upload        — Upload and process a document
    GET    /documents                — List all uploaded documents
    DELETE /documents/{document_id}  — Delete a document
    POST   /chat                     — Ask a question (RAG)
    GET    /chat/history             — Get conversation history
    POST   /chat/clear               — Clear conversation history
    POST   /documents/summarize      — Summarize a document
    POST   /documents/compare         — Compare multiple documents
    GET    /health                   — Health check
"""

import time
import os
import uuid
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from fastapi import Request
from fastapi import Response
from app.security import current_user, accessible_ids, require_document, workspace_id, scope_session
from app.database.models import DocumentAccess, DocumentProcessingJob
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.database.database import get_db
from app.database.models import Document
from app.models.schemas import (
    DocumentMetadata,
    DocumentListResponse,
    DocumentDeleteResponse,
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatHistoryItem,
    ClearChatResponse,
    SummarizeRequest,
    SummarizeResponse,
    CompareRequest,
    CompareResponse,
    HealthResponse,
    ErrorResponse,
)
from app.services.document_processor import DocumentProcessor
from app.services.rag_pipeline import RAGPipeline
from app.services.chat_memory import ChatMemoryService
from app.services.summarization_service import SummarizationService
from app.services.comparison_service import ComparisonService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()

# ── Service singletons (created once, reused across requests) ──
_document_processor: Optional[DocumentProcessor] = None
_rag_pipeline: Optional[RAGPipeline] = None
_chat_memory: Optional[ChatMemoryService] = None
_summarization_service: Optional[SummarizationService] = None
_comparison_service: Optional[ComparisonService] = None
_embedding_service: Optional[EmbeddingService] = None
_vector_store: Optional[VectorStore] = None


def get_document_processor() -> DocumentProcessor:
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def get_chat_memory() -> ChatMemoryService:
    global _chat_memory
    if _chat_memory is None:
        _chat_memory = ChatMemoryService()
    return _chat_memory


def get_summarization_service() -> SummarizationService:
    global _summarization_service
    if _summarization_service is None:
        _summarization_service = SummarizationService()
    return _summarization_service


def get_comparison_service() -> ComparisonService:
    global _comparison_service
    if _comparison_service is None:
        _comparison_service = ComparisonService()
    return _comparison_service


# Rate limiter is instantiated in main.py and applied as app-level middleware


# ── Document Endpoints ─────────────────────────────────────────

@router.post("/documents/upload", response_model=DocumentMetadata,
             status_code=status.HTTP_201_CREATED,
             summary="Upload and process a document")
async def upload_document(request: Request, response: Response, file: UploadFile = File(...), background: bool = False, user: str = Depends(current_user), db: Session = Depends(get_db)):
    """Upload a PDF, DOCX, or TXT file for processing.

    The file is:
    1. Validated (type, size)
    2. Saved to disk
    3. Text extracted and split into chunks
    4. Embeddings generated and stored in ChromaDB

    Returns the document metadata once processing is complete.
    """
    # Validate file type
    original_filename = Path((file.filename or "unnamed").replace("\\", "/")).name
    if len(original_filename) > 240:
        raise HTTPException(400, "Filename is too long.")
    file_type = original_filename.split(".")[-1].lower() if "." in original_filename else ""

    if f".{file_type}" not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{file_type}. Supported: PDF, DOCX, TXT",
        )

    # Read file content
    content = await file.read(settings.max_file_size_bytes + 1)
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(413, "File exceeds the configured size limit.")
    if file_type == "pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(400, "File is not a valid PDF.")
    if file_type == "docx":
        import io, zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist() or sum(i.file_size for i in archive.infolist()) > settings.max_file_size_bytes * 10:
                    raise ValueError()
        except (zipfile.BadZipFile, ValueError):
            raise HTTPException(400, "File is not a valid DOCX or is too large when expanded.")
    if file_type in {"txt", "md"} and b"\x00" in content:
        raise HTTPException(400, "Text files must not contain binary content.")
    file_size = len(content)

    # Validate file size
    valid, error_msg = get_document_processor().loader.validate_file(
        original_filename, file_size
    )
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Save file to disk
    save_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.{file_type}")
    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"File saved: {save_path} ({file_size} bytes)")

    if background:
        from app.services.processing_jobs import enqueue
        owner_workspace = workspace_id(request, user, db)
        document = Document(filename=original_filename, file_path=save_path,
            file_type=file_type, file_size=file_size, status="queued")
        db.add(document)
        db.flush()
        db.add(DocumentAccess(document_id=document.id, user_id=user, workspace_id=owner_workspace))
        enqueue(db, document.id)
        db.commit()
        response.status_code = 202
        return DocumentMetadata.model_validate(document)

    # Process the document through the full pipeline
    owner_workspace = workspace_id(request, user, db)
    def grant_document(id):
        from app.database.database import get_db_context
        with get_db_context() as grant_db:
            grant_db.add(DocumentAccess(document_id=id, user_id=user, workspace_id=owner_workspace))
            grant_db.commit()
    try:
        result = await run_in_threadpool(get_document_processor().process_upload,
            file_path=save_path,
            original_filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            on_created=grant_document,
        )
        if not db.get(DocumentAccess, result["id"]):
            db.add(DocumentAccess(document_id=result["id"], user_id=user, workspace_id=owner_workspace))
            db.commit()
        return DocumentMetadata(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Upload processing failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed. Check the server logs and your embedding model configuration.",
        )


@router.get("/documents", response_model=DocumentListResponse,
             summary="List all uploaded documents")
async def list_documents(request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    """Return all uploaded documents with their metadata."""
    documents = db.query(Document).filter(Document.id.in_(accessible_ids(request, user, db))).order_by(Document.created_at.desc()).all()
    stages = {job.document_id: job.stage for job in db.query(DocumentProcessingJob).filter(
        DocumentProcessingJob.document_id.in_([doc.id for doc in documents])).all()}

    doc_list = [
        DocumentMetadata(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            total_pages=doc.total_pages,
            total_chunks=doc.total_chunks,
            status=doc.status,
            error_message=doc.error_message,
            created_at=doc.created_at,
            extra_metadata=doc.metadata_json,
            processing_stage=stages.get(doc.id),
        )
        for doc in documents
    ]

    return DocumentListResponse(documents=doc_list, total=len(doc_list))


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse,
               summary="Delete a document")
async def delete_document(document_id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    require_document(document_id, request, user, db)
    job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
    if job and job.status in {"queued", "running"}:
        raise HTTPException(409, "Wait for document processing to finish before deleting it.")
    """Delete a document and all its associated chunks and files.

    This removes:
    - All embeddings from the vector store
    - The document metadata from the database
    - The file from disk
    """
    success = get_document_processor().delete_document(document_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    db.query(DocumentAccess).filter_by(document_id=document_id).delete()
    db.query(DocumentProcessingJob).filter_by(document_id=document_id).delete()
    db.commit()

    return DocumentDeleteResponse(
        success=True,
        message="Document deleted successfully",
        document_id=document_id,
    )


# ── Chat Endpoints ─────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse,
             summary="Ask a question about uploaded documents")
async def chat(request: ChatRequest, http_request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    allowed = accessible_ids(http_request, user, db)
    for id in request.document_ids or []:
        require_document(id, http_request, user, db)
    request.document_ids = request.document_ids or allowed or ["__no_documents__"]
    request.session_id = scope_session(request.session_id, http_request, user, db)
    """Ask a natural-language question and get a grounded answer.

    The answer is generated using RAG (Retrieval-Augmented Generation):
    1. The question is embedded and relevant chunks are retrieved
    2. The retrieved context is passed to the LLM
    3. The LLM generates an answer with source citations

    If the answer isn't in the documents, the response will say so.
    """
    try:
        result = await run_in_threadpool(get_rag_pipeline().answer_question,
            question=request.question,
            session_id=request.session_id,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )
        return ChatResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Chat failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Generation failed. Check your AI provider configuration and try again.",
        )


@router.get("/chat/history", response_model=ChatHistoryResponse,
             summary="Get conversation history")
async def get_chat_history(session_id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    session_id = scope_session(session_id, request, user, db)
    """Retrieve the chat history for a specific session."""
    memory = get_chat_memory()
    history = memory.get_history(session_id)

    messages = [
        ChatHistoryItem(
            role=msg["role"],
            content=msg["content"],
            sources=msg.get("sources"),
            timestamp=msg.get("timestamp"),
        )
        for msg in history
    ]

    return ChatHistoryResponse(
        session_id=session_id,
        messages=messages,
        total=len(messages),
    )


@router.post("/chat/clear", response_model=ClearChatResponse,
             summary="Clear conversation history")
async def clear_chat_history(session_id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    session_id = scope_session(session_id, request, user, db)
    """Delete all messages for a conversation session."""
    deleted = get_chat_memory().clear_history(session_id)

    return ClearChatResponse(
        success=True,
        message=f"Cleared {deleted} messages",
        session_id=session_id,
    )


# ── Summarization Endpoint ─────────────────────────────────────

@router.post("/documents/summarize", response_model=SummarizeResponse,
             summary="Summarize a document")
async def summarize_document(request: SummarizeRequest, http_request: Request, user: str = Depends(current_user),
                              db: Session = Depends(get_db)):
    require_document(request.document_id, http_request, user, db)
    """Generate a summary, key points, or definitions from a document.

    summary_type options:
    - comprehensive: Full summary
    - key_points: Bullet list of key takeaways
    - definitions: Extracted definitions and facts
    """
    # Verify document exists
    doc = db.query(Document).filter_by(id=request.document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {request.document_id}",
        )

    try:
        result = await run_in_threadpool(get_summarization_service().summarize,
            document_id=request.document_id,
            document_name=doc.filename,
            summary_type=request.summary_type,
            length=request.length,
        )
        return SummarizeResponse(**result)
    except Exception as exc:
        logger.error(f"Summarization failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Summarization failed. Check the configured AI provider and try again.",
        )


# ── Comparison Endpoint ────────────────────────────────────────

@router.post("/documents/compare", response_model=CompareResponse,
             summary="Compare multiple documents")
async def compare_documents(request: CompareRequest, http_request: Request, user: str = Depends(current_user),
                              db: Session = Depends(get_db)):
    for id in request.document_ids:
        require_document(id, http_request, user, db)
    """Compare 2-5 documents on a specified aspect.

    aspect options:
    - general: Overall comparison
    - methodology: Compare research methods
    - findings: Compare key findings
    - arguments: Compare main arguments
    """
    # Verify all documents exist
    for doc_id in request.document_ids:
        doc = db.query(Document).filter_by(id=doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {doc_id}",
            )

    try:
        result = await run_in_threadpool(get_comparison_service().compare,
            document_ids=request.document_ids,
            aspect=request.aspect,
        )
        return CompareResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Comparison failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comparison failed. Check the configured AI provider and try again.",
        )


# ── Health Check ───────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse,
             summary="Health check")
async def health_check():
    """Check the health of all system components."""
    from app.core.config import get_settings
    settings = get_settings()

    # Check database
    db_status = "healthy"
    try:
        from app.database.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check vector store
    vector_status = "healthy"
    try:
        vs = VectorStore()
        _ = vs.collection.count()
    except Exception:
        vector_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" and vector_status == "healthy" else "degraded",
        version=settings.app_version,
        database=db_status,
        vector_store=vector_status,
        embedding_model=settings.embedding_model_name,
        llm_backend=settings.llm_backend,
    )
