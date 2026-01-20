import sys
import json
import os
import logging
from openai import OpenAI
# Import config here to ensure env vars are loaded if needed
import config

# Note: We avoid top-level imports of .agent or .tools to prevent circular dependencies
# when this module is imported by tools.py

def run_worker(payload: dict) -> str:
    """
    Executes the subagent logic in the current process.
    designed to be called by ProcessPoolExecutor.
    """
    # Local imports to break cycles
    from .agent import RalphAgent
    from .tools import COMMON_TOOLS, AUTHOR_TOOLS

    api_key = payload.get("api_key")
    model = payload.get("model")
    instructions = payload.get("instructions")
    file_paths = payload.get("file_paths", [])
    subagent_id = payload.get("subagent_id", "Unknown")

    if not api_key:
        return "Error: Missing API Key"

    # Configure Logging for this worker (using a distinct logger per subagent might be noisy, 
    # but since we are in a process pool, basic config might conflict if not careful.
    # We'll rely on the parent process/standard logging or just print to stderr if needed for debugging.)
    # In a ProcessPool, logging setup in main might be inherited or need re-setup.
    # For now, we continue to use the established logger or just print logic from the original agent.

    # Initialize Client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Initial Context from file_paths
    initial_messages_content = ""
    from .tools import read_file 
    
    context_errors = []

    for path in file_paths:
        content = read_file(path)
        if content.startswith("Error"):
             context_errors.append(f"Failed to read {path}: {content}")
        else:
             initial_messages_content += f"\n--- FILE: {os.path.basename(path)} ---\n{content}\n"

    # Combine instructions with context
    system_prompt = f"""
    You are a Skilled Developer/Worker participating in a project.
    Your Manager has given you specific instructions.
    
    INSTRUCTIONS:
    {instructions}
    
    CONTEXT:
    {initial_messages_content}
    
    TOOLS:
    You have tools to READ and WRITE files. 
    You DO NOT have tools to run commands or build the project.
    
    GOAL:
    Perform the requested task (editing code, analyzing).
    When finished, output 'DONE' or if you think you need anything in environment before you can finish, output your request to manager.
    """

    # Subagent Tools: Common + Author
    SUBAGENT_TOOLS = COMMON_TOOLS + AUTHOR_TOOLS
    
    agent = RalphAgent(
        client=client,
        model=model,
        system_prompt=system_prompt,
        tools=SUBAGENT_TOOLS,
        name=f"Subagent-{subagent_id}"
    )

    agent.add_message("user", "Please start working on the instructions.")
    
    # We capture stdout/stderr to prevent cluttering the main terminal?
    # Actually, in ProcessPool, printing goes to the main stdout nicely usually.
    # The user wanted centralized management.
    # We will just run the loop.
    
    try:
        final_status = agent.run_loop(max_steps=config.SUBAGENT_MAX_STEPS) 
        last_message = agent.messages[-1].content
        return last_message
    except Exception as e:
        return f"Subagent Error: {str(e)}"

def main():
    """Legacy entry point for stdin/stdout usage (if needed)"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stderr
    )

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        return

    result = run_worker(input_data)
    print(json.dumps({"result": result}))

if __name__ == "__main__":
    main()
