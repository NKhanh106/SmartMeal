# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies only (no compiler)
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Set PATH to include user-installed binaries
ENV PATH=/root/.local/bin:$PATH

# Copy source code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts

# Create uploads directory with correct permissions
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app
USER appuser

# Health check — probes /health (no auth required)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Use migration + startup script (set execute permission on host before build)
ENTRYPOINT ["./scripts/migrate_and_start.sh"]
