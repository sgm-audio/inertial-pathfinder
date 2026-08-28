# Sonic Mind Forge - Cloud Run Dockerfile
# Multi-stage build with aggressive optimization

# ============================================================================
# Stage 1: Builder - Compile dependencies
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install only build essentials (minimal footprint)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (libsndfile, NO ffmpeg unless needed)
# Remove ffmpeg if not critical to reduce image by 500MB+
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user BEFORE copying files (better layer caching)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy pre-built wheels and install (single pip install for efficiency)
COPY --from=builder /build/wheels /tmp/wheels
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --no-index --find-links /tmp/wheels /tmp/wheels/* \
    && rm -rf /tmp/wheels

# Copy application code (smallest layer, copied last)
COPY --chown=appuser:appuser src/ ./src/

# Create storage directories with correct ownership in one layer
RUN mkdir -p uploads reports && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Optimize Python runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=2 \
    PORT=8080 \
    APP_ENV=production \
    DEBUG=false

EXPOSE 8080

# Lightweight health check (socket instead of urllib = faster)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8080), timeout=5).close()" || exit 1

# Run with uvloop for 2-4x faster async performance
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--loop", "auto"]
