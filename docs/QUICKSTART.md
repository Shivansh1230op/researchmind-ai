# Local quickstart (Windows PowerShell)

## Open the installed app

Double-click **Open ResearchMind.cmd** in the project folder. It starts the backend and frontend, checks their connection, and opens **http://localhost:3000/login** in your browser. Keep Node.js and the Python environment installed. If startup fails, logs are saved in `.researchmind-logs/`.

The document links in chat open source files in your editor; they are not the website address. Use the localhost address above for the running application.

New registrations require an emailed verification code. Configure a sending mailbox using [EMAIL_SETUP.md](EMAIL_SETUP.md). Existing accounts can still sign in; signup cannot send real codes until SMTP is configured.

Keep your existing `.env` private. Never paste keys into frontend files.

## Backend

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env  # only if .env does not already exist
$env:DEBUG = 'false'
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Frontend (another terminal)

```powershell
cd web
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:3000, launch the workspace and create an account. Upload a text-based PDF, DOCX, TXT, or Markdown file. Wait until it is ready, select it, and ask a question.

Uploads return after being queued. The library shows recorded processing stages while the worker extracts, chunks, embeds and indexes the file. Keep one API process running with `PROCESSING_WORKER_ENABLED=true`; queued jobs survive restarts. Run `alembic upgrade head` when updating an existing checkout to add the processing-job and conversation-title tables.

## Local generation with Ollama

Install Ollama separately, then run `ollama pull llama3.2:3b`. Set these **server-side** variables in `.env` and restart the backend:

```dotenv
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:3b
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
AUTH_REQUIRED=true
DEBUG=false
```

The first embedding call downloads the Sentence Transformers model. Download models while online before expecting offline operation. Do not change the embedding model for an existing Chroma collection; create a fresh collection and reprocess your files.

For OpenAI or an OpenAI-compatible provider, set `LLM_BACKEND=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and optional `OPENAI_BASE_URL`. Keys stay on the Python server. Gemini uses `LLM_BACKEND=gemini`. OpenAI, Ollama and Gemini now stream text incrementally; Hugging Face currently emits a complete generation event.

The worker warms one shared embedding model at startup (`PRELOAD_EMBEDDINGS=true`). Initial Python/model imports still take time on a cold start; later uploads and questions reuse the model. Quick Answer skips cross-encoder reranking. Deeper modes use the reranker only when its model files are cached, avoiding slow download retries.

## Checks

```powershell
.\venv\Scripts\python.exe -m pytest -m 'not integration'
cd web
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
```

Playwright uses installed Microsoft Edge locally. Set `CI=1` and install Chromium with `npx.cmd playwright install chromium` if Edge is unavailable. Browser tests mock API responses; the backend workflow test exercises real SQL, parsing, chunks and Chroma with external model calls mocked.

Run `pytest -m integration` separately to exercise real embeddings/vector retrieval. This requires installed model weights and sufficient RAM; model/network failures are not replaced with fake embeddings.
