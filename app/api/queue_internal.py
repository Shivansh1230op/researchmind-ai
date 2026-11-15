"""Private service-to-service queue callback, outside the public /api routes."""
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter()


class ProcessingMessage(BaseModel):
    document_id: str = Field(min_length=1, max_length=100)


@router.post("/internal/process-document", include_in_schema=False)
def process_document(body: ProcessingMessage, request: Request):
    settings = get_settings()
    expected = settings.internal_worker_secret
    provided = request.headers.get("authorization", "").removeprefix("Bearer ")
    if settings.processing_backend != "vercel_queue" or not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(404, "Not found.")
    from app.services.cloud_jobs import process_cloud_document
    process_cloud_document(body.document_id)
    return {"status": "processed"}
