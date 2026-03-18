# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Stage 1: dependency builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps in one layer
COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt \
 && pip install --no-cache-dir --prefix=/install \
        presidio-analyzer presidio-anonymizer spacy \
 # Download spaCy model into the install prefix so it ships in the image
 && python -m spacy download en_core_web_sm

# ---------------------------------------------------------------------------
# Stage 2: runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security: run as non-root
RUN groupadd --gid 1001 proxy \
 && useradd --uid 1001 --gid proxy --no-create-home --shell /sbin/nologin proxy

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local
# Copy spaCy model data
COPY --from=builder /usr/local/lib/python3.12/site-packages/en_core_web_sm \
                    /usr/local/lib/python3.12/site-packages/en_core_web_sm

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
