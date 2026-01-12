#!/bin/bash
# Run PAD Salience Annotation Prototype

PORT=${1:-8765}

echo "Starting PAD Salience Annotation Prototype..."
echo "Open http://localhost:$PORT/prototype/ in your browser"
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")"
python -m http.server $PORT
