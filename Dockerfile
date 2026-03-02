# ── agentik runner Docker image ─────────────────────────────────────────────────
#
# Provides the full agentik stack:
#   - Python 3.14 + runner dependencies
#   - opencode CLI (installed via official opencode.ai script)
#   - Node.js 24 LTS + pnpm (for Node/TS ecosystem projects)
#   - Git
#   - Pre-built web UI frontend
#
# Build:
#   docker build -t agentik .
#
# Run (interactive pipeline):
#   docker run -it --rm \
#     -v ./projects:/app/projects \
#     -e OPENCODE_API_KEY=<your-key> \
#     agentik --pipeline
#
# Run (web UI):
#   docker run -it --rm \
#     -v ./projects:/app/projects \
#     -p 8420:8420 \
#     -e OPENCODE_API_KEY=<your-key> \
#     agentik --web --host 0.0.0.0
#
# See docker-compose.yml for the recommended way to run.

FROM python:3.14-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# ── System packages ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# ── opencode CLI (official installer from opencode.ai) ────────────────────────
# The installer puts the binary in $HOME/.opencode/bin and only appends it to
# shell rc files, which are never sourced in Docker RUN steps.
# Pre-add the install location to PATH so the binary is found immediately.
ENV PATH="/root/.opencode/bin:${PATH}"
RUN curl -fsSL https://opencode.ai/install | bash \
    && opencode version

# ── Node.js + pnpm (for Node/TS ecosystem projects) ───────────────────────────
ENV NODE_MAJOR=24
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable \
    && corepack prepare pnpm@latest --activate

# Point pnpm content store to a named-volume mount point so it persists across
# rebuilds and stays off bind-mounted project directories (huge speedup on
# Windows/macOS Docker where bind-mount I/O is slow).
ENV PNPM_STORE_DIR=/pnpm-store
RUN mkdir -p /pnpm-store /pnpm-vstore \
    && pnpm config set store-dir /pnpm-store

# ── Workspace setup ───────────────────────────────────────────────────────────
WORKDIR /app

# Install Python dependencies first (layer cache).
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi "uvicorn[standard]"

# Copy the rest of the source.
COPY agentik.py budget.json check_roadmap.py opencode.jsonc ./
COPY runner/ runner/
COPY web/__init__.py web/_pipeline_worker.py web/app.py web/
COPY helpers/ helpers/
COPY prompts/ prompts/
COPY tests/ tests/
COPY AGENTS.md README.md ROADMAP_EXAMPLE.md LICENSE ./

# Create projects mount point.
RUN mkdir -p projects

# ── Pre-build the web frontend ─────────────────────────────────────────────────
# Vite outputs directly to ../static (= /app/web/static/) via outDir config.
COPY web/frontend/ web/frontend/
RUN cd web/frontend \
    && corepack enable \
    && corepack prepare pnpm@latest --activate \
    && pnpm install --frozen-lockfile \
    && pnpm run build \
    && test -f /app/web/static/index.html \
    && echo "Frontend build OK — $(ls /app/web/static/assets/*.js | wc -l) JS chunks"

# ── Runtime ────────────────────────────────────────────────────────────────────
EXPOSE 8420

# Default: launch the web UI dashboard.
ENTRYPOINT ["python", "agentik.py"]
CMD ["--web", "--host", "0.0.0.0"]
