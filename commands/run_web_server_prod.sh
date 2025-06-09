#!/bin/sh

# Running Gunicorn with Uvicorn workers
gunicorn src.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    --graceful-timeout 60 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50
