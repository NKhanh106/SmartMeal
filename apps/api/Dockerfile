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

# Fix ownership so appuser can read user-installed packages
RUN chown -R appuser:appuser /root/.local

# Set PATH and PYTHONPATH so pip's alembic takes priority over /app/alembic
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib/python3.12/site-packages

# Copy source code
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY scripts ./scripts

# Fix alembic shim shebang — it uses system python3.12 but alembic is in user packages.
# After this, the shim will call /usr/local/bin/python which respects PYTHONPATH.
RUN chmod +x /root/.local/bin/alembic && \
    chmod +x scripts/migrate_and_start.sh

# Create uploads directory with correct permissions
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

# Health check — probes /health (no auth required)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Use migration + startup script
ENTRYPOINT ["./scripts/migrate_and_start.sh"]
