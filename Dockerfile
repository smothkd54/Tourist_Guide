# Pushkinskaya Street Explorer — backend container
FROM python:3.11-slim

WORKDIR /app

# System deps for Pillow/TensorFlow + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY backend/ ./backend/
COPY data/landmarks.json ./data/landmarks.json
COPY data/photos/ ./data/photos/
COPY models/ ./models/
COPY frontend/ ./frontend/
COPY preflight_check.py .

ENV PYTHONUNBUFFERED=1
ENV CORS_ORIGINS=http://localhost:*|http://127.0.0.1:*
ENV GUNICORN_WORKERS=2
ENV MODEL_PATH=/app/models/landmark_classifier.keras
EXPOSE 5000

# Don't run as root in production
RUN useradd -m appuser && chown -R appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Fail fast and loud if required artifacts are missing, instead of
# starting a server that silently returns 503 on every /predict call.
CMD python preflight_check.py && gunicorn -w ${GUNICORN_WORKERS:-2} -b 0.0.0.0:5000 backend.app:app
