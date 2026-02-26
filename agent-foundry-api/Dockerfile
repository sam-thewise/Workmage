FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x worker-entrypoint.sh
ENV PYTHONPATH=/app

# Non-root user for Celery worker (avoids "running with superuser privileges" warning)
# Docker GID 999 is common on Linux; if worker can't access docker socket, match host: ls -n /var/run/docker.sock
RUN groupadd -g 999 docker 2>/dev/null || true && \
    useradd -m -u 1000 celeryuser && \
    usermod -aG docker celeryuser 2>/dev/null || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
