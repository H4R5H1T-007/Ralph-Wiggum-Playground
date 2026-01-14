# Ralph Agent

A standalone implementation of the Ralph code generation method with Acceptance-Driven Backpressure, designed for OpenRouter.

## Setup

1.  **Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Copy `.env.example` to `.env` and add your OpenRouter API Key.
    ```bash
    cp .env.example .env
    # Edit .env
    ```

### 1. Start Workspace
Before running the agent, make sure the workspace container is running:
```bash
docker-compose up -d
```
This starts an Alpine Linux container that mounts your `workspace/`.

### 2. Planning Mode
Run this to generate or update your implementation plan based on specs.
```bash
./loop.sh plan
```
*   **Input**: `workspace/specs/*.md`
*   **Output**: `workspace/IMPLEMENTATION_PLAN.md`

### 2. Building Mode
Run this to implement the tasks continuously (TDD style).
```bash
./loop.sh build
```
*   **Input**: `workspace/IMPLEMENTATION_PLAN.md`
*   **Action**: Runs tests (Docker), Writes code, Commits (Simulated/Real).

## Directory Structure available to Agent
*   `workspace/`: The **ONLY** directory the agent can write to. Put your source code and specs here.
*   `internal/`: The agent's source code (Read-Only to Agent).
*   `prompts/`: The system prompts (Read-Only to Agent).
