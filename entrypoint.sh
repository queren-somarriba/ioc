#!/bin/bash
set -e
rm -rf /tmp/ollama_ready

ollama serve &
SERVE_PID=$!
trap 'kill "$SERVE_PID"; wait "$SERVE_PID"' TERM INT

echo "Waiting for Ollama to start..."
until ollama list > /dev/null 2>&1; do
  sleep 1
done

echo "Downloading models: qwen2.5:3b & qwen2.5-coder:3b"
ollama pull qwen2.5:3b
ollama pull qwen2.5-coder:3b

touch /tmp/ollama_ready
wait "$SERVE_PID"