# syntax=docker/dockerfile:1
#
# Capstone — UW Bothell Course Advisor
# -----------------------------------
# Builds a self-contained image of the app. Ollama is expected to run
# on the host (the image defaults OLLAMA_HOST to host.docker.internal),
# so the multi-GB model weights are NOT baked into the image. On Linux,
# pass --add-host=host.docker.internal:host-gateway to docker run, or
# point OLLAMA_HOST at your Ollama address explicitly.

FROM python:3.12-slim AS base

# ── System deps ───────────────────────────────────────────────────────
# - poppler-utils  : pdfplumber's PDF rendering backend
# - libxml2-dev    : selectolax's HTML parser
# - build-essential: optional, for any wheel that needs to compile
# - tini           : clean PID 1 / signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
      poppler-utils \
      libxml2-dev \
      tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --shell /bin/bash capstone
USER capstone
WORKDIR /home/capstone/app

# ── Install Python deps first (layer caching) ─────────────────────────
COPY --chown=capstone:capstone pyproject.toml ./
COPY --chown=capstone:capstone src ./src
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --user --no-cache-dir -e ".[ui,llm,turso]"
ENV PATH="/home/capstone/.local/bin:${PATH}"

# ── App config + bundled artifacts ────────────────────────────────────
COPY --chown=capstone:capstone config.yaml ./
COPY --chown=capstone:capstone README.md ARCHITECTURE.md ./

# ── Runtime config ────────────────────────────────────────────────────
# Persistent DB path — mount a volume here to keep the catalog between runs.
RUN mkdir -p /home/capstone/data
ENV CAPSTONE_DB=/home/capstone/data/capstone.db \
    PYTHONUNBUFFERED=1 \
    OLLAMA_HOST=http://host.docker.internal:11434 \
    CAPSTONE_SKIP_FIRSTRUN=1

VOLUME ["/home/capstone/data"]
EXPOSE 8765

# ── Healthcheck (no LLM required) ─────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
                 r=urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=3); \
                 sys.exit(0 if r.status==200 else 1)" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]

# Two-step start: bootstrap the catalog if needed, then serve.
# Override by setting CMD on `docker run` if you want a different command.
CMD ["sh", "-c", "python -m capstone.deploy.boot && uvicorn capstone.api:app --host 0.0.0.0 --port ${PORT:-8765}"]
