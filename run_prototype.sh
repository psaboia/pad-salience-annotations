#!/bin/bash
# Run PAD Salience Annotation Server

PORT=${1:-8765}

echo "Starting PAD Salience Annotation Server..."
echo "Open http://localhost:$PORT in your browser"
echo "Press Ctrl+C to stop"
echo ""
echo "Data will be saved to: data/annotations.jsonl"
echo "Audio files saved to: data/audio/"
echo ""

cd "$(dirname "$0")"
uv run python server.py
