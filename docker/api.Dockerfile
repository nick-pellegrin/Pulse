FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer)
COPY api/pyproject.toml api/uv.lock* ./
RUN uv sync --frozen --no-install-project

# Copy source
COPY api/ .

EXPOSE 8000

CMD ["uv", "run", "fastapi", "run", "src/pulse_api/main.py", "--host", "0.0.0.0", "--port", "8000"]
