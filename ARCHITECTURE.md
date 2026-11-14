# DocuMind AI — System Architecture

## Overview

DocuMind AI is a production-quality RAG (Retrieval-Augmented Generation) document intelligence platform. Users upload PDFs, Word documents, and text files, then ask natural-language questions and receive answers grounded in those documents with source citations.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Streamlit)                      │
│  ┌───────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Sidebar   │  │  Chat Panel   │  │  Source Citation Panel │ │
│  │  Upload    │  │  Q&A History  │  │  Document Preview      │ │
│  └─────┬─────┘  └──────┬───────┘  └───────────┬────────────┘ │
└────────┼───────────────┼──────────────────────┼─────────────┘
         │               │                      │
         ▼               ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    API Routes                            ││
│  │  /upload  /documents  /delete  /chat  /history  /summarize││
│  └──────────────────────────┬──────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Business Logic Layer                    ││
│  │  ┌────────────┐ ┌──────────────┐ ┌────────────────────┐││
│  │  │ Document   │ │  RAG Pipeline │ │ Summarization      │││
│  │  │ Loader     │ │               │ │ & Comparison       │││
│  │  └─────┬──────┘ └───────┬───────┘ └────────────────────┘││
│  │  ┌────────────┐ ┌──────┴───────┐ ┌────────────────────┐││
│  │  │  Text      │ │  Embedding    │ │  Vector Store      │││
│  │  │  Splitter  │ │  Service      │ │  (ChromaDB)        │││
│  │  └────────────┘ └──────────────┘ └────────────────────┘││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Data Layer                              ││
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  ││
│  │  │ SQLAlchemy  │  │ ChromaDB     │  │ Session Memory  │  ││
│  │  │ + SQLite    │  │ Vector Store │  │ (per-session)   │  ││
│  │  └────────────┘  └──────────────┘  └────────────────┘  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         │                                           
         ▼                                          
┌─────────────────┐     ┌──────────────────────┐
│  OpenAI API     │     │  Sentence Transformers │
│  (LLM +         │     │  (Embeddings)           │
│   Embeddings)   │     │                        │
└─────────────────┘     └──────────────────────┘
```

---

## 2. Project Folder Structure

```
documind-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # All API endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Settings from environment variables
│   │   └── logging_config.py      # Structured logging setup
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_loader.py     # PDF/DOCX/TXT extraction
│   │   ├── text_splitter.py       # Configurable chunking
│   │   ├── embedding_service.py   # Embedding generation
│   │   ├── vector_store.py        # ChromaDB operations
│   │   ├── retrieval_service.py   # Semantic + hybrid search
│   │   ├── rag_pipeline.py        # End-to-end RAG orchestration
│   │   ├── chat_memory.py         # Conversation history
│   │   ├── summarization_service.py
│   │   └── comparison_service.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic request/response models
│   └── database/
│       ├── __init__.py
│       ├── database.py            # SQLAlchemy engine/session
│       └── models.py              # ORM models
├── frontend/
│   └── app.py                     # Streamlit UI
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_document_loader.py
│   ├── test_text_splitter.py
│   ├── test_embedding_service.py
│   ├── test_vector_store.py
│   ├── test_retrieval_service.py
│   ├── test_rag_pipeline.py
│   ├── test_api_routes.py
│   └── test_chat_memory.py
├── data/
│   ├── uploads/                   # Uploaded files storage
│   ├── chroma_db/                 # Vector database persistence
│   └── sample_documents/         # Example documents for testing
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── pytest.ini
└── README.md
```

---

## 3. Data Flow Diagram

```
                    ┌──────────────┐
                    │  User Upload  │
                    │  (PDF/DOCX/TXT)│
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Document Loader│
                    │ Extract text +  │
                    │ metadata        │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Text Splitter  │
                    │ Chunk + overlap│
                    │ Preserve pages │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Embedding      │
                    │ Service        │
                    │ (Sentence      │
                    │  Transformers) │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Vector Store   │
                    │ (ChromaDB)      │
                    │ Store vectors   │
                    │ + metadata      │
                    └──────────────┘

                    ┌──────────────┐
                    │  User Question │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Embed Question │
                    │ (same model)   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Retrieval      │
                    │ Service        │
                    │ Top-K + filter │
                    │ + rerank       │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ RAG Pipeline   │
                    │ Build prompt   │
                    │ + context       │
                    │ + memory        │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ LLM (OpenAI)  │
                    │ Generate answer│
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Response      │
                    │ Answer +       │
                    │ citations +    │
                    │ source excerpts│
                    └──────────────┘
```

---

## 4. Technology Choices

| Component         | Choice                     | Why                                                    |
|-------------------|----------------------------|--------------------------------------------------------|
| Web Framework     | FastAPI                    | Async, auto-docs (Swagger), Pydantic validation        |
| RAG Framework     | LangChain                 | Mature, composable, wide integrations                  |
| LLM               | OpenAI GPT                 | Best-in-class reasoning, reliable API                  |
| Embeddings        | Sentence Transformers      | Local, free, no API calls, good quality                 |
| Vector DB         | ChromaDB                   | Embedded, no server needed, persistent, metadata filter  |
| Relational DB     | SQLite + SQLAlchemy        | Zero-config dev, PostgreSQL-ready via connection string  |
| Frontend          | Streamlit                  | Rapid Python UI, good for ML/data apps                 |
| Validation        | Pydantic                   | Type-safe schemas, auto-validation                     |
| Testing           | Pytest                     | Python standard, fixtures, parametrize                 |
| Containerization  | Docker + Compose           | Reproducible, easy deployment                           |

---

## 5. Security Considerations

- API keys stored in `.env`, never exposed to frontend
- File type validation (whitelist: PDF, DOCX, TXT)
- File size restrictions (configurable, default 50MB)
- Malformed PDF handling with graceful errors
- Per-session conversation isolation
- Prompt injection mitigation (document content treated as data, not instructions)
- Structured logging for audit trails
- Rate limiting on API endpoints
