FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ingestion-specific code
COPY src ./src

# Copy shared backend code (database, models, allocation, ingestion, etc.)
# This is done at runtime via volumes in docker-compose, but we need to prepare the directory structure
RUN mkdir -p /app/src/database /app/src/allocation /app/src/ingestion /app/src/scheduler /app/src/anomaly /app/src/utils

# Create non-root user
RUN useradd -m -u 1000 finops && chown -R finops:finops /app
USER finops

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/api/v1/health')" || exit 1

# Run application (ingestion backend)
CMD ["uvicorn", "src.app_ingest:app", "--host", "0.0.0.0", "--port", "8001"]
