# Pushkinskaya Street Explorer — backend container
FROM python:3.11-slim@sha256:0a236bf8f0b6013383df04d1cd02cb0abe5fbfa1a7012141d7ff9202b7cb30a6

WORKDIR /app

# System deps for Pillow/TensorFlow + curl for healthcheck
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY . .
RUN pip install --no-cache-dir .
RUN pip uninstall -y setuptools wheel

ENV PYTHONUNBUFFERED=1
ENV CORS_ORIGINS=http://localhost:*|http://127.0.0.1:*
ENV GUNICORN_WORKERS=2
ENV MODEL_PATH=/app/models/landmark_classifier.tflite
ENV LOG_DIR=/app/logs
EXPOSE 5000

# Don't run as root in production
RUN useradd -m appuser && chown -R appuser /app
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs
USER appuser

# Run migrations + seed (when DATABASE_URL is set), verify artifacts, serve.
RUN chmod +x /app/scripts/entrypoint.sh

# Model loading happens at import inside each worker; on a slow host that
# can exceed gunicorn's default 30 s boot timeout. Allow a generous boot
# window, and give the healthcheck time for the first model load.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
