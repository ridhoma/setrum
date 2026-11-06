# Use Astral's official uv + Python 3.13 slim image
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Configure Python and uv
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    SETRUM_DB_PATH=/app/data/setrum.db \
    SETRUM_CACHE_DIR=/tmp/setrum-cache \
    PORT=8050

# Install curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code
COPY . .

# Finalize uv installation
RUN uv sync --frozen --no-dev

# Ensure data directory exists for persistent sqlite and cache
RUN mkdir -p /app/data

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8050/health || exit 1

CMD ["uv", "run", "gunicorn", "run:server", "--bind", "0.0.0.0:8050", "--workers", "2", "--threads", "2"]
