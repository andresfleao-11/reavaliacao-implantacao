#!/bin/sh
# Start script for Railway deployment
# Uses PORT from environment, defaults to 8000

PORT="${PORT:-8000}"
echo "Starting uvicorn on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
