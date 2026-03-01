# ── agentik runner Docker image ─────────────────────────────────────────────────
#
# Provides the full agentik stack:
#   - Python 3.12 + runner dependencies
#   - opencode CLI (installed via official opencode.ai script)
#   - Node.js + pnpm (for Node/TS ecosystem projects)
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

FROM python:3.12-slim AS base

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
ENV NODE_MAJOR=22
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable \
    && corepack prepare pnpm@latest --activate

# ── Workspace setup ───────────────────────────────────────────────────────────
WORKDIR /app

# Install Python dependencies first (layer cache).
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi "uvicorn[standard]"

# Copy the rest of the source.
COPY agentik.py budget.json check_roadmap.py opencode.jsonc ./
COPY runner/ runner/
COPY helpers/ helpers/
COPY prompts/ prompts/
COPY tests/ tests/
COPY AGENTS.md README.md ROADMAP_EXAMPLE.md LICENSE ./

# Create projects mount point.
RUN mkdir -p projects

# ── Pre-build the web frontend (if node_modules are present) ──────────────────
COPY runner/web/frontend/ runner/web/frontend/
RUN cd runner/web/frontend \
    && npm install \
    && npm run build \
    && mkdir -p /app/runner/web/static \
    && cp -r dist/* /app/runner/web/static/ \
    || echo "Frontend build skipped (optional)"

# ── Runtime ────────────────────────────────────────────────────────────────────
EXPOSE 8420

# Default: launch the web UI dashboard.
ENTRYPOINT ["python", "agentik.py"]
CMD ["--web", "--host", "0.0.0.0"]
