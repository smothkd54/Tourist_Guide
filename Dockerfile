# Pushkinskaya Street Explorer — backend container
FROM python:3.11-slim

WORKDIR /app

# System deps for Pillow/TensorFlow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/landmarks.json ./data/landmarks.json
COPY data/photos/ ./data/photos/
COPY models/ ./models/
COPY frontend/ ./frontend/
COPY preflight_check.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Don't run as root in production
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Fail fast and loud if required artifacts are missing, instead of
# starting a server that silently returns 503 on every /predict call.
CMD python preflight_check.py && python backend/app.py