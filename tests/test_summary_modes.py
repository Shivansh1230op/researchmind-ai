"""Summary controls must change real provider inputs and preserve sources."""
from unittest.mock import MagicMock
import pytest
from app.models.schemas import SummarizeRequest
from app.services.summarization_service import SummarizationService


@pytest.mark.parametrize("mode", ["short", "comprehensive", "executive", "bullet_points", "academic", "chapters", "key_points", "beginner", "definitions"])
def test_summary_styles_use_actual_source_and_budget(mode):
    store, llm = MagicMock(), MagicMock()
    store.collection.get.return_value = {"ids": ["c1"], "documents": ["Measured 42 observations."],
        "metadatas": [{"page_number": 7, "chunk_index": 0}]}
    llm.generate_response.return_value = "The study measured 42 observations (page 7)."
    service = SummarizationService(vector_store=store, llm_service=llm)
    assert SummarizeRequest(document_id="doc", summary_type=mode).summary_type == mode
    result = service.summarize("doc", "paper.pdf", mode, length="short")
    call = llm.generate_response.call_args.kwargs
    assert "Measured 42 observations." in call["user_prompt"]
    assert "[Page 7]" in call["user_prompt"]
    assert "180 words" in call["user_prompt"] and call["max_tokens"] == 512
    assert result["sources"][0]["page_number"] == 7
    assert result["sources"][0]["document_id"] == "doc"


def test_long_source_truncation_is_disclosed():
    store, llm = MagicMock(), MagicMock()
    store.collection.get.return_value = {"ids": ["c1"], "documents": ["x" * 60000], "metadatas": [{"chunk_index": 0}]}
    llm.generate_response.return_value = "Partial summary."
    result = SummarizationService(store, llm).summarize("doc", "long.md", "academic", "long")
    assert result["truncated"] is True
    assert "truncated for length" in llm.generate_response.call_args.kwargs["user_prompt"]
    assert llm.generate_response.call_args.kwargs["max_tokens"] == 2600
