FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=appuser:appuser . .

ENV PORT=7860
ENV PYTHONUNBUFFERED=1

USER appuser
EXPOSE 7860

CMD ["python", "hf_entrypoint.py"]
