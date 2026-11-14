"""Regression checks for warm model reuse and incremental provider streaming."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService


def test_embedding_instances_share_cached_model_without_network():
    name = "performance-test-model"
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = 384
    constructor = MagicMock(return_value=model)
    with patch.dict(sys.modules, {"sentence_transformers": SimpleNamespace(SentenceTransformer=constructor),
                                 "torch": SimpleNamespace(set_num_threads=MagicMock())}):
        try:
            a, b = EmbeddingService(name), EmbeddingService(name)
            assert a.model is b.model
            constructor.assert_called_once_with(name, local_files_only=True)
        finally:
            EmbeddingService._models.pop(name, None)


def test_gemini_yields_first_chunk_before_reading_remainder():
    service = LLMService()
    service.backend, service.api_key, service.model_name = "gemini", "test-only", "test-model"
    response = MagicMock()
    consumed = []

    def lines(**kwargs):
        assert kwargs["chunk_size"] == 1
        consumed.append(1)
        yield 'data: ' + json.dumps({"candidates": [{"content": {"parts": [{"text": "First "}]}}]})
        consumed.append(2)
        yield 'data: ' + json.dumps({"candidates": [{"content": {"parts": [{"thought": True, "text": "private"}, {"text": "answer"}]}}]})

    response.iter_lines.side_effect = lines
    response.__enter__.return_value = response
    with patch("requests.post", return_value=response) as post:
        stream = service.stream_response("system", "question", max_tokens=512)
        assert next(stream) == "First "
        assert consumed == [1]
        assert list(stream) == ["answer"]
        assert post.call_args.kwargs["stream"] is True
        assert post.call_args.kwargs["json"]["generationConfig"]["maxOutputTokens"] == 512
        assert "test-only" not in post.call_args.args[0]


def test_quick_retrieval_skips_cross_encoder_but_preserves_sources():
    embedding, store = MagicMock(), MagicMock()
    store.search.return_value = [{"content": "Supported finding", "metadata": {"document_id": "owned", "chunk_index": 0}, "similarity_score": .95}]
    retrieval = RetrievalService(embedding, store)
    retrieval.enable_reranking = True
    with patch.object(retrieval, "_rerank") as rerank:
        results = retrieval.retrieve("finding", document_ids=["owned"], rerank=False)
    rerank.assert_not_called()
    assert results[0].document_id == "owned"
    assert store.search.call_args.kwargs["document_ids"] == ["owned"]
