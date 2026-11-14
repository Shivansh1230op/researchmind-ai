"""SSE transport for actual retrieval and provider generation."""
import json
import re
import time
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database.database import get_db, get_db_context
from app.database.models import ConversationSession
from app.models.schemas import ChatRequest
from app.security import current_user, accessible_ids, require_document, scope_session, workspace_id

router = APIRouter()
MODES = {
    "quick": "Give a concise, direct answer.",
    "deep": "Synthesize the evidence across documents, discuss agreements and gaps in detail.",
    "simple": "Explain for a beginner using plain language and supported examples.",
    "critical": "Critically evaluate supported limitations, inconsistencies and open questions. Separate evidence from interpretation.",
    "summary": "Provide a structured research summary: objective, methods, findings, limitations and takeaways. Mark unavailable information.",
    "compare": "Compare the documents on methodology, findings and limitations. Only include supported information and identify missing data.",
}


@router.post("/chat/stream")
def stream_chat(body: ChatRequest, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from app.api.routes import get_rag_pipeline
    allowed = accessible_ids(request, user, db)
    for id in body.document_ids or []:
        require_document(id, request, user, db)
    ids = body.document_ids or allowed or ["__no_documents__"]
    if body.mode == "compare" and len(set(ids)) < 2:
        raise HTTPException(422, "Select at least two documents to compare.")
    internal_id = scope_session(body.session_id, request, user, db)
    session_label = f"{user}:{workspace_id(request, user, db)}:{body.session_id}"

    def events():
        def event(kind, data):
            return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        try:
            started = time.perf_counter()
            yield event("status", {"stage": "Searching documents"})
            pipeline = get_rag_pipeline()
            retrieved = pipeline.retrieval_service.retrieve(query=body.question,
                top_k=body.top_k or (15 if body.mode in {"deep", "compare"} else 5), document_ids=ids,
                rerank=body.mode in {"deep", "compare", "critical"})
            retrieval_ms = round((time.perf_counter() - started) * 1000)
            sources = pipeline._build_sources(retrieved)
            yield event("sources", sources)
            answer = ""
            if not retrieved:
                answer = "I couldn't find relevant information in the selected documents. Upload or select documents related to your question."
                yield event("token", {"text": answer})
            else:
                yield event("status", {"stage": "Generating grounded answer"})
                context = pipeline._build_context(retrieved)
                prompt = pipeline._build_user_prompt(body.question, context)
                # Citation labels are verified against the actual retrieved set.
                system = pipeline.SYSTEM_PROMPT + "\n" + MODES[body.mode] + "\nUse numbered citation labels [1], [2], etc., matching Source numbers in context. Never cite a number outside that set."
                history = pipeline.memory_service.get_history_messages(internal_id, limit=10)
                for token in pipeline.llm_service.stream_response(system, prompt, history,
                        max_tokens=512 if body.mode == "quick" else None):
                    answer += token
                    yield event("token", {"text": token})
            yield event("status", {"stage": "Checking source references"})
            answer = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m[1]) <= len(sources) else "[reference unavailable]", answer)
            pipeline.memory_service.add_message(internal_id, "user", body.question)
            pipeline.memory_service.add_message(internal_id, "assistant", answer, sources=sources)
            with get_db_context() as session:
                row = session.query(ConversationSession).filter_by(session_id=internal_id).first()
                if row:
                    row.title = session_label
                    session.commit()
            yield event("done", {"answer": answer, "sources": sources, "session_id": body.session_id,
                "no_answer_found": not retrieved or pipeline._check_no_answer(answer),
                "timings": {"retrieval_ms": retrieval_ms, "total_ms": round((time.perf_counter() - started) * 1000)}})
        except GeneratorExit:
            raise
        except Exception:
            from app.core.logging_config import get_logger
            get_logger(__name__).exception("Streaming generation failed")
            yield event("error", {"message": "Research failed. Check the configured AI provider and embedding model, then retry."})

    return StreamingResponse(events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
