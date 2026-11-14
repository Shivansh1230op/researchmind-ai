"""Small synthetic provider probe. Prints timings only, never credentials."""
import time
from app.services.llm_service import LLMService

started = time.perf_counter()
first = None
chars = 0
try:
    for chunk in LLMService().stream_response("Return only the requested word.", "Reply with READY.", max_tokens=16):
        if first is None:
            first = time.perf_counter() - started
        chars += len(chunk)
    print({"first_chunk_seconds": round(first, 3) if first else None,
           "total_seconds": round(time.perf_counter() - started, 3), "characters": chars})
except Exception as exc:
    print({"provider_probe": "failed", "error_type": type(exc).__name__})
    raise SystemExit(1)
