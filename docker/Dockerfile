# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Stage 1: dependency builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps and download the spaCy model in the builder stage.
COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir presidio-anonymizer \
 && python -m spacy download en_core_web_sm

# ---------------------------------------------------------------------------
# Stage 2: runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security: run as non-root
# Create group and user only if they don't already exist
RUN groupadd --gid 1001 proxy 2>/dev/null || true \
 && useradd --uid 1001 --gid proxy --no-create-home --shell /sbin/nologin proxy 2>/dev/null || true

WORKDIR /app

# Copy installed packages and downloaded spaCy model from builder
COPY --from=builder /usr/local /usr/local

# Copy application source
COPY src/       ./src/
COPY config/    ./config/

# Create log dir owned by proxy user (volume-mount point)
RUN mkdir -p /app/logs && chown proxy:proxy /app/logs

# Drop to non-root
USER proxy

# Read-only filesystem: only /app/logs is writable (mounted as volume)
# Enforce via docker run --read-only --tmpfs /tmp

EXPOSE 8080

# Prefer uvicorn with 2 workers; override via CMD in compose for dev
CMD ["uvicorn", "src.proxy.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2", \
     "--no-access-log"]