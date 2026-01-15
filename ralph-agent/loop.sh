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
MAX_ITERATIONS=${2:-1} # Default to 1 iteration if not specified. Set to 0 for infinite.

if [ -z "$MODE" ]; then
    echo "Usage: ./loop.sh [plan|build] [iterations]"
    exit 1
fi

ITERATION=0

while true; do
    # Check iteration limit
    if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "Reached max iterations: $MAX_ITERATIONS"
        break
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Running Ralph in $MODE mode (Iteration $((ITERATION+1)))"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    python3 -m internal.main "$MODE"
    
    ITERATION=$((ITERATION + 1))
    
    # Optional: Short pause or check for git changes? 
    # For now, just immediate restart as per playbook.
done
