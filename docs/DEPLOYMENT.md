# Deploy the complete ResearchMind application

The root `Dockerfile` now builds the website and Python API into **one service**.
Open the service's public URL to use the app; `/api` automatically reaches the
private Python process. You do not need a separate backend URL for this setup.
Use a Docker-capable host such as Render or Railway, or a VPS with Docker.

To prepare a clean source ZIP for upload to GitHub, run
`python infra/package_deployment.py`. It creates `dist/ResearchMind-deploy.zip`
without your local `.env`, documents/databases, or installed dependencies.
Extract it and upload its contents to the repository root. Keep the `.github`
folder when uploading if you want the included container build checks.

## Render

1. Put this project's source in a GitHub repository. Include `Dockerfile`, `web/`,
   `app/`, `infra/`, both requirements files, and `render.yaml`. Keep `.env`,
   `venv`, `node_modules`, `.next`, and your local `data/` out of Git.
2. In Render, choose **New → Blueprint**, connect that repository, and review
   `render.yaml`. It defines one Docker web service with a 2 GB compute plan and
   a 5 GB disk. **These are paid resources; review the displayed price before
   creating them.** This memory choice is a starting point, not a measured limit
   under concurrent document processing.
3. Enter the prompted private values using your existing local settings:
   `OPENAI_MODEL`, `OPENAI_API_KEY`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and
   `SMTP_FROM_EMAIL`. The default provider is Gemini. To use a different provider,
   change `LLM_BACKEND` and its model/settings together.
4. Deploy, then open the public service URL. Its default Render origin is
   automatically allowed for authenticated actions. If you attach a custom
   domain, set `PUBLIC_URL=https://your-domain.example` and redeploy.

The disk is mounted at `/data` and preserves accounts, uploaded files, Chroma
indexes, and the downloaded embedding cache. Keep one service instance.

## Railway

With the current Gmail SMTP delivery, Railway requires its **Pro plan or above**.
Its Free, Trial, and Hobby plans block outbound SMTP. Check the
[official email-delivery policy](https://docs.railway.com/networking/outbound-networking)
before choosing this host for OTP registration.

1. Create a project from the GitHub repository, keeping its root directory at
   the repository root. `railway.json` selects the root Dockerfile and readiness
   check automatically. Do not set a separate start command.
2. Attach a persistent volume mounted at `/data`. The deployment requires this
   mount, and the config file does not create the volume for you.
3. Add the private AI and Gmail SMTP variables from `.env.production.example`.
   Supply real values through Railway's Variables UI, not source files.
4. Generate a public domain. `RAILWAY_PUBLIC_DOMAIN` supplies the default allowed
   origin. For custom domains, set `PUBLIC_URL` or add all permitted origins to
   the comma-separated `CORS_ORIGINS` variable.
5. Deploy and open the public domain. The launcher listens on Railway's `PORT`.
   The private API reserves port `8765`; use another port for the public server.

## Any Docker host / local container preview

Build and start from the repository root:

```sh
docker build -t researchmind-ai .
docker run --rm -p 3000:3000 --env-file .env.production \
  -v researchmind-data:/data researchmind-ai
```

Create `.env.production` privately using `.env.production.example` and fill in
your credentials. For an HTTP preview on your own computer, set
`PUBLIC_URL=http://localhost:3000` and `COOKIE_SECURE=false`. For a live HTTPS
site, use its actual origin and `COOKIE_SECURE=true`. The public port defaults
to 3000 and follows `PORT` when your host supplies it. Route public traffic to
that port; the API port `8765` remains private.

On a VPS, put the container behind your HTTPS reverse proxy, preserve `/data`,
and pass `PUBLIC_URL` with the external HTTPS origin. No public `API_PROXY_URL`
is needed: the container embeds its loopback API target at build time.

## Netlify frontend with a separately hosted backend

Netlify can still build the frontend from `web/` with `netlify.toml`. Follow
[the Netlify guide](NETLIFY_DEPLOYMENT.md). For a backend-only Docker build, use:

```sh
docker build --target backend -t researchmind-api .
```

Configure the container host's Docker target as `backend` (or deploy that built
image). Set its public `PORT`, persistent database/upload/Chroma paths, secure
cookies, and `CORS_ORIGINS` to the Netlify origin. Set Netlify's build-time
`API_PROXY_URL` to that backend's HTTPS origin. The existing `docker compose up
--build` also uses this backend target and keeps the local two-service setup.

## First deployment checks

1. Wait for the host's deployment to become healthy. `/api/ready` checks API and
   database availability without requiring an AI request. The embedding model
   downloads/warms up separately, so the first document can take longer.
2. Open `/login`, register, receive the email OTP, verify, and sign in.
3. Upload a small document and check that processing reaches Ready.
4. Ask a question and verify its answer streams with source references.
5. Restart the service and confirm your account and document are still present.

Gmail SMTP needs a valid App Password and a host that allows outbound SMTP.
Render's Free services also block Gmail SMTP ports and do not support persistent
disks; the supplied paid Blueprint avoids those Free-plan restrictions. See
[Render's Free service limits](https://render.com/docs/free).
Use the same account for `SMTP_USERNAME` and `SMTP_FROM_EMAIL` unless you've
configured a verified Gmail sending alias. The image keeps credentials out of
the browser and image layers; only the runtime receives them.

The build installs CPU PyTorch wheels and omits local Streamlit/test packages.
It still downloads Next.js dependencies, fonts, and Python packages, so the
first image build requires network access and takes longer than a cached build.
Do not choose a static-only host for the complete container. If a host cannot
provide persistent storage or blocks Gmail SMTP, use a suitable service/plan.
For multiple workers/replicas, replace the local queue and storage design first.

Official references: [Render Blueprints](https://render.com/docs/blueprint-spec),
[Render persistent disks](https://render.com/docs/disks),
[Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles), and
[Railway volumes](https://docs.railway.com/volumes).
