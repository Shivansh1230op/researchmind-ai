# Deploy ResearchMind on Netlify

Netlify hosts the Next.js frontend in `web/`. The existing FastAPI service needs
a separate, continuously running Python/container host: it owns authentication,
email OTP, document processing, AI requests, and persistent files and databases.
Deploying the frontend alone does not start this backend.

## 1. Prepare the Python backend

Build the root Dockerfile's `backend` target on a container host
(`docker build --target backend -t researchmind-api .`), or install
`requirements-server.txt` and run:

```sh
uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

Set `PORT` to the port expected by your host. The backend image defaults to port
8000 and respects the host's `PORT`. The default Docker target instead bundles
the complete website and API: see [single-service deployment](DEPLOYMENT.md).
Use one API process/replica while using the built-in processing worker.

Configure these variables on the **backend host**:

```dotenv
DEBUG=false
AUTH_REQUIRED=true
COOKIE_SECURE=true
CORS_ORIGINS=https://YOUR-SITE.netlify.app
DATABASE_URL=sqlite:////data/documind.db
UPLOAD_DIR=/data/uploads
CHROMA_PERSIST_DIR=/data/chroma_db
```

Replace the origin with your actual Netlify site or custom domain. Multiple
allowed origins are comma-separated. Mount persistent storage at `/data` for
these example paths. Ensure the host can download the embedding model and has
enough memory to load it; an ephemeral filesystem loses accounts and documents
on a restart or redeploy.

Copy your AI/provider and Gmail SMTP settings from your local `.env` into the
backend host's private environment settings. Keep `.env` out of Git and keep
credentials out of all `NEXT_PUBLIC_*` variables.

Before connecting the frontend, verify the public HTTPS backend URL returns a
successful response at `/ready`. Allow the initial model warm-up to finish.

## 2. Connect the repository to Netlify

Push the project source, including the root `netlify.toml`, to your Git provider
and import that repository in Netlify. Use a Git-connected build so Netlify can
build Next.js and run its adapter. A manual upload of the source folder does not
perform that build.

The checked-in configuration selects:

| Setting | Value |
| --- | --- |
| Base directory | `web` |
| Build command | `npm run build` |
| Publish directory (relative to base) | `.next` |
| Node.js | `22` |
| Browser API path | `/api` |

Netlify automatically configures its Next.js adapter. Keep the repository's
`web/package-lock.json` committed. Do not use `out`, `public`, or the repository
root as the publish directory for this app, and do not add an SPA `/*` fallback.

In Netlify's environment variables, add this variable with build access:

```dotenv
API_PROXY_URL=https://YOUR-BACKEND-HOST
```

Use the backend origin with no trailing slash or `/api` suffix. The checked-in
Next.js rewrite maps `/api/auth/...` to the backend's `/auth/...`, for example.
`localhost`, `127.0.0.1`, and Docker's `backend` hostname are only reachable in
their local environments and do not reach your laptop from Netlify.

Start a new deploy after changing `API_PROXY_URL`: Next.js embeds the rewrite
target during the build. Keep browser requests on `/api` so authentication uses
the frontend's same-origin cookie flow.

## 3. Check the live site

1. Open `https://YOUR-SITE.netlify.app/api/ready` and confirm the backend is ready.
2. Register with an email address, receive its OTP, and verify the account.
3. Upload a small document, wait for indexing, and ask a question.

If the frontend build fails, inspect Netlify's deploy log and share the first
actual error and nearby lines. If pages load but login/upload fails, check
`API_PROXY_URL`, backend readiness, and `CORS_ORIGINS` first. A successful frontend
build does not verify the Python service or its Gmail/AI credentials.

References: [Netlify Next.js support](https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/)
and [Netlify subdirectory build settings](https://docs.netlify.com/build/configure-builds/monorepos/).
