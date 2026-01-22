#!/bin/bash

# Get the directory where the script is located (ralph_graph/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check if .env exists in ralph_graph
if [ ! -f "ralph_graph/.env" ]; then
    echo "Error: ralph_graph/.env file not found."
    exit 1
fi
    
# Virtual Environment Setup
if [ ! -d "ralph_graph/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv ralph_graph/.venv
fi

source ralph_graph/.venv/bin/activate

# Install Dependencies
if [ -f "ralph_graph/requirements.txt" ]; then
    echo "Installing/Updating dependencies..."
    pip install -q -r ralph_graph/requirements.txt
fi

MAX_ITERATIONS=${1:-1} # Default to 1 iteration if not specified. Set to 0 for infinite.

ITERATION=0

# Initialize Workspace Container
echo "Initializing Workspace..."
# We run as a module so imports work
python -m ralph_graph.startup

while true; do
    # Check iteration limit
    if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "Reached max iterations: $MAX_ITERATIONS"
        break
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Running Ralph Graph (Iteration $((ITERATION+1)))"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    python -m ralph_graph.main
    
    ITERATION=$((ITERATION + 1))
done
