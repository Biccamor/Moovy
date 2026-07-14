# ============================================
# Stage 1: Builder — install dependencies
# ============================================
FROM python:3.11.9-slim AS builder

WORKDIR /app

# Install build dependencies needed for some pip packages (e.g. psycopg2-binary)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /app/requirements.txt

# ============================================
# Stage 2: Runtime — lean production image
# ============================================
FROM python:3.11.9-slim AS runtime

WORKDIR /app

# Only runtime C libs, no compiler
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN useradd -m appuser && \
    mkdir -p /home/appuser/.cache/huggingface && \
    chown -R appuser:appuser /home/appuser/.cache

COPY --chown=appuser:appuser . /app/

USER appuser

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]

# ============================================
# Stage 3: Dev — runtime + dev tools (CI/local)
# ============================================
FROM runtime AS dev

USER root

COPY ./requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010", "--reload"]
