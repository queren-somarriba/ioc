#!/bin/bash
ollama serve &

echo "Attente du démarrage d'Ollama..."
until ollama list > /dev/null 2>&1; do
  sleep 1
done

echo "Downloading models: qwen2.5:3b & qwen2.5-coder:3b"
ollama pull qwen2.5:3b && ollama pull qwen2.5-coder:3b

wait