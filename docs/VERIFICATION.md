# Local verification — 14 November 2026

| Check | Result |
| --- | --- |
| Pytest excluding model integration tests | 98 passed, 28 deselected |
| Full API workflow | Passed using real SQL, text parsing, chunks and Chroma; embedding and generation calls mocked |
| User/workspace authorization, session revocation, origin checks | Passed |
| Source citation SSE and invalid-label handling | Passed |
| PDF, DOCX and Markdown report output | Passed; binary signatures verified |
| TypeScript check | Passed |
| Next.js production build | Passed |
| Playwright in Microsoft Edge | 10 passed; includes signup/OTP screens, mobile error handling, summary controls, passage inspection, conversation management, processing-stage polling and current-edit export |
| Additive Alembic migration | `upgrade head` and `current` passed through `0002_jobs_preferences` against an isolated local database |
| Persistent ingestion jobs | Real extraction/chunking/indexing with recorded stages, stable document IDs, safe errors, retry and restart recovery passed; model embeddings mocked |
| Summary generation controls | All nine styles, source page labels, three length budgets, truncation disclosure and batch authorization tested |
| npm dependency audit | 0 reported vulnerabilities after compatible fixes |
| Screenshot inspection | Overview and research workspace captured and visually inspected |

The browser tests use mocked API responses. They complement the backend API workflow test; they are not a live-provider browser end-to-end test. Real-model suites were attempted but interrupted after slow execution; no complete pass is claimed for the 28 marked integration tests. No paid AI request was needed for the verified checks. Ollama generation, Docker execution, PostgreSQL and production deployment are not verified.

## Performance follow-up

The latency fix was checked with a real cached `all-MiniLM-L6-v2` model and one tiny synthetic Gemini request (no uploaded document content). Warm second-service query embedding took 0.045 seconds and reused the same model instance. A batch of 64 synthetic passages took 3.531 seconds. Cold imports plus the first embedding took 77.176 seconds in the initial isolated process, so startup warmup was added; it does not eliminate cold-start costs. The Gemini probe received its first five-character text chunk in 2.094 seconds and finished in 2.143 seconds. These are individual local checks, not full-PDF or full-answer latency guarantees.

Regression tests verify shared model loading, cache-first loading without remote checks, actual incremental Gemini SSE consumption, and skipping the cross-encoder for quick retrieval while preserving document filters. A previously queued document was confirmed ready, and the running backend was restarted with working provider network access. Windows logging no longer emits Unicode encoding tracebacks for every HTTP request.

Gemini streaming contract: https://ai.google.dev/api/generate-content#method:-models.streamgeneratecontent

Initial checks exposed and fixed a missing RAG answer-cleaning method, nullable canvas TypeScript errors, simulated processing stages, public document endpoints, nonfunctional collections/history/search, single-candidate retrieval score normalization, a clipped empty-chat welcome state, unsafe upload filenames, overly permissive credentialed CORS, and vulnerable frontend transitive dependencies.

Google Fonts downloads required network-enabled builds. The final Edge run completed successfully and included actual interface screenshots; the product screenshot on the landing page uses that captured empty workspace, not fabricated research data.


Email OTP signup: four lifecycle tests plus an SMTP transport test pass. OTP browser flows cover code entry, incorrect-code feedback, resend cooldown, email changes, unavailable delivery and mobile layout. Sender SMTP settings are absent on this server; real mailbox delivery remains unverified and cannot work until configured. The signup migration was applied.
## Visual polish follow-up

The dashboard now includes a lightweight decorative research constellation, refined cards, improved font usage, hover treatments and a consistent login/chat finish. Framer Motion follows the user's reduced-motion preference. Desktop dark/light and mobile screenshots were captured from the running production app with isolated fixture data and visually inspected; the mobile page has no horizontal overflow.

All eleven browser scenarios were verified across the production checks and targeted retries. The initial concurrent development/build checks hit timing failures in this Windows environment; the summary and upload-polling cases passed when rerun with software rendering. The test configuration now supports an existing server via `PLAYWRIGHT_BASE_URL` and otherwise checks a production build. Run `npm run build` before `npm test`.

## Deployment packaging follow-up

- The full frontend production build passed with `/api` pointing to the container's private API port. It used an isolated `.next-deploy` directory; the normal local build and original TypeScript configuration were preserved.
- Official Render and Railway JSON schema validation passed for the deployment manifests. Railway requires the `/data` volume; Render's Blueprint defines a persistent disk and paid compute.
- The non-integration backend suite passed: 114 tests, 28 deselected. The final deployment test file separately passed all 17 tests, including source-package exclusion of credentials and runtime data.
- Actual Next.js standalone and FastAPI processes were started through the deployment supervisor on Windows, using an isolated temporary database. Public readiness, the login page, CSS assets, proxied cookie login, allowed-origin workspace creation, rejection of an untrusted origin, logout/session revocation, and workspace persistence across a full process restart all passed. Both child services were stopped afterward.
- Docker is unavailable on this machine, so the Linux image build and container runtime were not executed locally. A GitHub Actions workflow builds the actual image and checks the public website/API readiness and restart when run. No live host was created or deployed, and hosted Gmail/AI delivery remains to be checked after runtime credentials are configured.

