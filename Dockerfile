# One public service: Next.js proxies /api to the private Python process.
FROM node:22-bookworm-slim AS node-runtime

FROM node-runtime AS web-build
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=/api \
    API_PROXY_URL=http://127.0.0.1:8765
RUN npm run build

FROM python:3.11-slim-bookworm AS python-build
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-server.txt ./
# CPU wheels avoid downloading CUDA libraries on ordinary hosting servers.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-server.txt \
    && pip check

FROM python:3.11-slim-bookworm AS python-runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libgomp1 libstdc++6 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-build /usr/local/bin /usr/local/bin
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBUG=false \
    AUTH_REQUIRED=true
RUN mkdir -p /app/data/uploads /app/data/chroma_db /app/data/sample_documents

# Separate API deployment for Netlify and the existing two-service Compose setup.
FROM python-runtime AS backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/ready',timeout=5)"
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

# Default target: deploy the complete application as a single Docker service.
FROM python-runtime AS fullstack
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=web-build /build/web/.next/standalone ./web/
COPY --from=web-build /build/web/.next/static ./web/.next/static/
COPY --from=web-build /build/web/public ./web/public/
COPY infra/start.py ./infra/start.py
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    COOKIE_SECURE=true \
    DATABASE_URL=sqlite:////data/documind.db \
    UPLOAD_DIR=/data/uploads \
    CHROMA_PERSIST_DIR=/data/chroma_db \
    HF_HOME=/data/huggingface
ENV EMBEDDING_CPU_THREADS=2 \
    ENABLE_RERANKING=false
RUN mkdir -p /data/uploads /data/chroma_db /data/huggingface
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','3000')+'/api/ready',timeout=5)"
CMD ["python", "infra/start.py"]
