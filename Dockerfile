FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (recommended for Hugging Face Spaces)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire repository
COPY --chown=appuser:appuser . .

ENV PORT=7860
USER appuser
EXPOSE 7860

CMD ["sh", "-c", "uvicorn mock_backend:app --host 0.0.0.0 --port ${PORT}"]
