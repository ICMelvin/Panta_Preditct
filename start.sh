#!/bin/bash
set -e

echo "Starting PantaPredict services..."

# Start the Telegram bot in the background
echo "Starting Telegram bot..."
python -m bot.bot &
BOT_PID=$!

# Wait a moment for the bot to start
sleep 2

# Start the FastAPI backend in the foreground
# Use PORT from environment variable (Render sets this), fallback to 8000
echo "Starting FastAPI backend on port ${PORT:-8000}..."
uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} &
UVICORN_PID=$!

# Monitor both processes - if either dies, exit the container
while true; do
  if ! kill -0 $BOT_PID 2>/dev/null; then
    echo "Telegram bot process died, exiting container"
    kill $UVICORN_PID 2>/dev/null || true
    exit 1
  fi
  if ! kill -0 $UVICORN_PID 2>/dev/null; then
    echo "Uvicorn process died, exiting container"
    kill $BOT_PID 2>/dev/null || true
    exit 1
  fi
  sleep 1
done
