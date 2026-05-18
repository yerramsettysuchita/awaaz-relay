# Build context: project root
# Usage via compose: docker compose up --build
# Usage standalone: docker build -f backend/Dockerfile -t awaaz-backend .

FROM python:3.11-slim

# curl is used by the HEALTHCHECK instruction
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# --- Dependency layer (cached unless requirements.txt changes) ---
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Application source (invalidates on any .py change) ---
COPY backend/ .

# --- Security: run as non-root ---
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data \
    && chown -R appuser /app
USER appuser

EXPOSE 8000

# Docker-native health check — used by compose depends_on: condition: service_healthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
