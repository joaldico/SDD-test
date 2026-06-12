# syntax=docker/dockerfile:1
# Marketplace Conciliator — API image (plan 3.8.1)
#
# Two stages:
#   builder  — python:3.12-slim + gcc; builds the project wheel and collects
#              all runtime dependency wheels into /wheels.
#   runtime  — python:3.12-slim only; copies wheels, installs them, drops
#              to a non-root user; no compiler, no build toolchain, no cache.
#
# Secrets and credentials are NEVER baked into this image.
# They are injected via environment variables at container startup (12-factor).

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# gcc is required by some transitive C-extension dependencies:
#   - uvloop  (uvicorn[standard] → better async performance)
#   - cryptography (added in T-2.x for Argon2)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the project manifest and source code
COPY pyproject.toml ./
COPY src/ ./src/

# Build the project wheel and download all runtime dependency wheels.
# pip wheel resolves the full dependency tree and stores all .whl files in
# /wheels — nothing is installed in this stage.
RUN pip install --no-cache-dir wheel \
    && pip wheel --no-cache-dir --wheel-dir=/wheels .

# ── Stage 2: runtime (non-root, no compiler, no build artefacts) ─────────────
FROM python:3.12-slim AS runtime

# Non-root system user — plan 3.8.1 / T-1.4 DoD
RUN groupadd --system --gid 1001 appgroup \
    && useradd  --system --uid 1001 --gid 1001 --no-create-home appuser

WORKDIR /app

# Install from the pre-built wheel cache: no network call, no compiler
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
      marketplace-conciliator-api \
    && rm -rf /wheels

USER appuser:appgroup

EXPOSE 8000

# Container-level liveness probe (also used by Docker Compose healthcheck)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health').read()"

# 1 worker: BackgroundTasks jobs hold in-process state (ADR-002).
# Scaled to multiple instances via load balancer, not multiple workers.
CMD ["uvicorn", "marketplace_conciliator.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1"]
