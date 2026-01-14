#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and set your keys."
    exit 1
fi

MODE=$1

if [ -z "$MODE" ]; then
    echo "Usage: ./loop.sh [plan|build]"
    exit 1
fi

echo "Running Ralph in $MODE mode..."
python3 -m internal.main "$MODE"
