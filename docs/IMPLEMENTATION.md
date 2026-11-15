# ResearchMind implementation and verification

The `app/` FastAPI backend and `web/` Next.js client power the authenticated research workspace.

## Implemented

- Full application deployment on Vercel Services, with PostgreSQL/pgvector, Gemini embeddings, private Blob uploads and a private queue consumer. The [live deployment guide](VERCEL_DEPLOYMENT.md) records the production URL, successful live checks and verification limits.

- Account registration, scrypt password hashing, HttpOnly cookies, server-side revocation, login/logout, origin checking and protected dashboard.
- User-owned workspaces, workspace-scoped document listing, retrieval, reports and conversations. Original source URLs enforce document ownership even without a workspace header.
- PDF/DOCX/TXT/Markdown ingestion with bounded reads, randomized storage names, signature/archive checks, text extraction, page metadata, chunking, local embeddings and persistent ChromaDB.
- Real provider streaming for OpenAI-compatible APIs, Ollama and Gemini. Hugging Face currently returns a complete generation event rather than simulated tokens.
- Backend-derived retrieval/generation/citation-label events. The UI never cycles fictional processing stages.
- Chat modes change generation instructions; deep research increases retrieval count. Compare mode requires multiple documents.
- Clickable retrieved passage cards, original PDF viewer, conversation resume, Markdown export, copy, regenerate and abort.
- Workspace document statistics and upload-date activity, dedicated summarization and comparison, similarity graph with pan/zoom/node dragging/search.
- Persisted editable research reports with Markdown, paginated PDF and DOCX downloads. References preserve retrieved titles, available page numbers and excerpts.
- Responsive sidebar, mobile document/source panels, keyboard search, theme persistence, reduced motion, loading and error states.
- CI checks, additive migrations and local/Vercel environment examples.
- Persistent single-process document queue with recorded extraction/chunking/embedding/indexing stages, restart recovery, retry and real status polling.
- Conversation renaming/deletion and empty-workspace deletion controls; all remain scoped to the current owner/workspace.
- Nine summarization styles, three length budgets, up to ten selected documents, visible truncation disclosure and inspectable source passages.
- Report exports save the editor contents first so downloads include the latest edits.
- Upload/chat services share one embedding model. Cached weights load without remote checks, and the worker warms the model at startup. Quick Answer skips the optional cross-encoder and uses a 512-token budget; deeper modes retain optional cached reranking.

## Architectural choices

SQLAlchemy with SQLite and ChromaDB provides a lightweight single-server development configuration. The Vercel deployment uses PostgreSQL for metadata and vectors, pgvector cosine ranking, Gemini embeddings and private Vercel Blob storage. Retrieval combines vector candidates with keyword rescoring and, locally, an optional cross-encoder; it does not implement independent corpus-wide BM25 or HyDE. Canvas and CSS supply ambient graphics without a Three.js dependency. Native React state and fetch keep the existing frontend dependency footprint small. These are deliberate substitutions, not claims that every requested library is used.

## Remaining limitations

This is a functional development implementation, not a verified production SaaS. The following requested capabilities need additional work:

- New signup uses expiring email OTP verification with TLS-protected SMTP delivery, resend limits and hashed codes. SMTP credentials must be configured before real signup can send email. Password reset delivery is not implemented.
- The local web client submits background uploads (`?background=true`) to a persistent SQL queue and polls recorded stages. Its worker supports one API process. On Vercel, direct private Blob uploads feed Vercel Queues and a secured Python processing callback; database locks coordinate concurrent deliveries. Celery/Redis execution is not included. The synchronous upload API remains available for compatibility.
- Scanned PDF OCR is not included. Preprocess scans using OCR before uploading. DOCX/TXT/Markdown have logical text blocks rather than reliable printed page numbers.
- Summarization supports short, detailed, executive, bullet, academic, chapter/section, key-findings, beginner and definitions styles. Length controls set prompt targets and token budgets; they do not guarantee an exact word count. Batch output summarizes each selected document separately.
- Citation checks validate source-label bounds and preserve retrieved passage provenance. They cannot verify that every generated claim is supported; human source verification remains necessary. Retrieved source cards are evidence candidates, not a guarantee of model correctness.
- Graph edges represent embedding similarity only, not extracted factual entities or causal relationships. Graph processing is capped at 100 documents and 200 passages each.
- Report synthesis uses up to 20 retrieved passages and a bounded context; it is not exhaustive full-corpus literature review. Summarization and comparison truncate long source text and disclose truncation in the provider prompt.
- No bibliographic citation-style conversion, external academic search, S3 storage, team sharing, billing, notification system, autosave, or dedicated mathematical equation renderer.
- Document rename/reprocessing, empty-workspace deletion and session rename/deletion have UI controls. Workspaces with documents, reports or conversations cannot be deleted until emptied. User profile editing is not exposed.
- In-memory rate limiting is per process. Multi-worker/distributed deployment needs Redis-backed limiting and coordinated job execution.
- Existing legacy documents are never silently assigned to a registered user. Re-upload into an owned workspace, or use explicit `AUTH_REQUIRED=false` only on a trusted loopback server for legacy local access.
- Live provider generation and deployment must be checked separately from mocked API tests. The frontend build, browser interaction tests, dependency audit and additive migration were verified locally. See the [Vercel deployment guide](VERCEL_DEPLOYMENT.md) for the successful live checks and remaining verification limits.

## Deployment boundary

The Next.js frontend and Python service share one HTTPS origin. On Vercel, Services routes requests to the appropriate service and private storage preserves data across deployments. The Vercel entrypoint sets secure cookies and allowed deployment origins. Local development uses a same-origin proxy and stores SQLite/Chroma files under the ignored data directory. See [Vercel deployment](VERCEL_DEPLOYMENT.md) for the full cloud architecture.

Provider compatibility reference: https://docs.ollama.com/api/openai-compatibility

Migration reference: https://alembic.sqlalchemy.org/en/latest/tutorial.html
