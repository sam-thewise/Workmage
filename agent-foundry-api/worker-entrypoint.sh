#!/bin/sh
# Run Celery as non-root: create celeryuser, chown volume, drop privileges.
# Docker adds us to DOCKER_GID via group_add for socket access.
groupadd -g 999 docker 2>/dev/null || true
useradd -m -u 1000 celeryuser 2>/dev/null || true
chown -R 1000:1000 /agent-runs 2>/dev/null || true
exec celery -A app.worker.celery_app worker --loglevel=info --uid=1000 --gid=1000
