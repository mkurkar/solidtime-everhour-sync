FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system --no-cache .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app
USER appuser

# Config is mounted at runtime
VOLUME ["/app/data"]

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
    CMD python -c "import requests; print('ok')" || exit 1

CMD ["python", "-m", "solidtime_everhour.main"]
