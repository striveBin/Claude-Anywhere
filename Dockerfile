FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv once and cache dependency resolution separately from source code.
RUN pip install --no-cache-dir --upgrade pip uv

# README is referenced by pyproject, so include it during dependency sync.
COPY pyproject.toml uv.lock README.md ./

# Create the project environment from the lockfile.
RUN uv sync --locked --no-dev

# Copy the application source after dependencies to maximize Docker layer cache hits.
COPY . .

EXPOSE 8082

CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8082"]
