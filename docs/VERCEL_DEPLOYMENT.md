# Deploy the entire ResearchMind app on Vercel

The root `vercel.json` defines a Next.js website and a Python FastAPI service
under one Vercel project and domain. No Render, Railway or VPS service is needed.
Vercel Services and Queues currently use beta platform features. Review the
resources and current prices in your account before creating paid resources.

## Live deployment — 15 November 2026

Production URL: **https://researchmind-ai-five.vercel.app**

The application is deployed in the owner's Vercel Hobby project. Neon Free
PostgreSQL and a private Vercel Blob store are connected in Singapore. Runtime
AI and SMTP settings are stored in private Production variables. Source was
deployed from the local workspace with the Vercel CLI; GitHub auto-deploy is not
connected. Future changes can be published with `vercel deploy --prod` from this
linked repository root after appropriate checks.

Live checks passed for the public homepage/login/readiness endpoints, cookie
login, authenticated direct multipart Blob upload, queue-driven TXT and PDF
extraction/indexing, private source downloads, rejection of anonymous source
access, streamed AI answers and source citations. Synthetic documents and the
temporary accounts were removed. Direct database locks were also checked for
cross-connection exclusion and release. No OTP emails were sent during testing;
real mailbox delivery and large-file limits remain unverified.

## Architecture

- `website`: Next.js from `web/`, with a private binding to the backend.
- `backend`: Python 3.12 from the repository root, using `index:app` and the
  lightweight dependencies in `pyproject.toml` / `uv.lock`.
- `/api/*` routes directly to FastAPI. `/api/blob-upload` routes to the website
  for authorized Blob client tokens. Other paths route to Next.js.
- Accounts, workspaces, conversations, reports, reservations, jobs and vectors
  live in PostgreSQL connected through Vercel Storage/Marketplace. The database
  provider (for example Neon) runs the database; Vercel runs all application code.
- Original documents live in a **private Vercel Blob store**. Browser multipart
  uploads bypass Function body-size limits and retain the app's 50 MB limit.
  Each upload requires a signed-in account and a workspace-specific reservation.
- Vercel Queues invokes a private Node.js consumer. It calls the Python processing
  endpoint over the service binding with an internal authorization secret. Python
  downloads the source into a unique temporary directory, extracts text, calls
  Gemini embeddings, persists chunks and cleans up the temporary copy. SQL jobs
  record real stages. The processing endpoint is outside public `/api` routing.
- pgvector ranks document-filtered vectors inside PostgreSQL. Chunks are stored
  durably as JSON, cast to pgvector for exact cosine search; there is currently
  no approximate-nearest-neighbor index. Query work grows with the selected corpus.
- Cross-encoders and local embedding weights are disabled in the cloud profile.
  Gemini text embeddings are normalized to 768 dimensions by default. Existing
  local Chroma indexes are not compatible and are not uploaded automatically.

## Deploy

1. Connect the Vercel integration, or sign into Vercel and import the GitHub
   repository. **Keep the Project Root Directory at the repository root (`.`),
   not `web`.** The root service configuration owns both application parts.
   Do not override the services with a single Next.js framework setting.
2. From the project's Storage tab, connect a PostgreSQL database that supports
   the `vector` extension. Set `DATABASE_URL` to the provider's pooled URL with
   TLS enabled. `postgres://` and `postgresql://` URLs are normalized to psycopg.
   Keep `DATABASE_URL_UNPOOLED` connected too: session locks use that direct URL
   so transaction pooling cannot change the connection that owns a job's lock.
   Use separate databases for Preview and Production to isolate their data.
3. Create a **Private** Vercel Blob store. Include the read-write-token variable
   when connecting it so `BLOB_READ_WRITE_TOKEN` is available. The token is used
   server-side to sign narrow client upload tokens; it never reaches the browser.
4. Add the AI and SMTP variables from `.env.vercel.example` through Vercel's
   private environment settings. A Gemini embedding key is required even if a
   different provider handles generation. Never put secrets in `NEXT_PUBLIC_*`.
5. Generate a random `INTERNAL_WORKER_SECRET` and store it as a private Production
   variable. Deploy using the root `vercel.json`; its website service registers
   the queue trigger for `src/app/api/queue/process/route.ts`. No public worker
   endpoint or continuously running API thread is required. Ensure Queues/Services are
   enabled for the account. The current Functions budget is 300 seconds.
6. If using a custom domain, set `PUBLIC_URL` to its HTTPS origin. The standard
   production, branch and deployment Vercel origins are added automatically.
   `API_PROXY_URL` is not needed for this deployment.

The Vercel entrypoints reject SQLite configuration instead of silently saving
accounts on temporary disk. Cold starts initialize additive tables behind a
PostgreSQL advisory lock. They also enable the pgvector extension, so the initial
database role must have permission to do so, or an administrator must enable it
before deploying. For managed schema changes use the additive Alembic migrations.

## Verify the deployed app

1. `/api/ready` returns `{"status":"ready"}`.
2. Register, receive a real email OTP, verify it and sign in.
3. Upload a small document; observe queued/extracting/embedding/indexing/ready.
4. Ask a question, check streamed citations, open its private source, and export
   a report. Repeat with a file larger than 4.5 MB to verify direct Blob upload.
5. Redeploy and confirm the account, source, document index and history persist.
6. Sign into another account and verify it cannot open the original source.

Queue deliveries retry failures up to three times; completed deliveries are
idempotent. PostgreSQL session advisory locks prevent two Functions from
processing/deleting the same document at once and release after process death.
If scheduling fails, the saved document is marked failed and its library Retry
action schedules it again. Documents that exceed the Function's time limit may
need smaller source files or a larger supported duration on the selected plan.

## Verification boundaries

Local verification on 15 November 2026:

- The non-integration backend suite passed: 122 tests, 28 deselected.
- The final nine cloud tests passed on an isolated Python 3.12.13 environment
  using the locked Vercel dependencies, including real route requests against
  the cloud entrypoint without importing PyTorch, Chroma or Sentence Transformers.
- TypeScript checks and a production Next.js build with `VERCEL=1` passed.
- The running production server returned 200 for login and 403 for an unauthorized
  Blob upload authorization request; the temporary server was then stopped.
- The service manifest passed Vercel's current JSON schema validation. The
  frontend dependency audit reported zero vulnerabilities after a compatible
  transitive Zod and minimatch updates.
- The deployment ZIP contains the cloud entrypoints, SDK lockfile and service
  configuration, and excludes local credentials, user documents and databases.

Local tests exercise real SQL persistence, extraction/chunking, ownership,
reservation expiry, duplicate completion, retries, source-copy cleanup and
remote embedding requests with provider/storage transports mocked. SQLite is
used for these adapter tests. The live PostgreSQL, Blob, queue and AI checks are
listed above; real SMTP mailbox delivery remains to be checked separately.

The existing global HTTP rate limiter remains per Function instance. Use a shared
rate-limit store before scaling untrusted public traffic. Abandoned upload
reservations and their orphaned blobs currently require periodic cleanup.

Sources: [Services](https://vercel.com/docs/services),
[service routing](https://vercel.com/docs/services/routing),
[service bindings](https://vercel.com/docs/services/bindings),
[Python Functions](https://vercel.com/docs/functions/runtimes/python),
[Blob client uploads](https://vercel.com/docs/vercel-blob/client-upload),
[Blob Python SDK](https://vercel.com/docs/vercel-blob/python-sdk-reference),
[Queues](https://vercel.com/docs/queues/quickstart),
[Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings).
