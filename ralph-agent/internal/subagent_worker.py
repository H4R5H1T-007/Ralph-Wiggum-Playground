import sys
import json
import os
import logging
from openai import OpenAI
from .agent import RalphAgent
from .tools import COMMON_TOOLS, AUTHOR_TOOLS

def main():
    # Configure logging to output to stderr (which parent captures)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stderr
    )

    # Read input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        return

    api_key = input_data.get("api_key")
    model = input_data.get("model")
    instructions = input_data.get("instructions")
    file_paths = input_data.get("file_paths", [])
    subagent_id = input_data.get("subagent_id", "Unknown")

    if not api_key:
        print(json.dumps({"error": "Missing API Key"}), file=sys.stderr)
        return

    # Initialize Client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Initial Context from file_paths
    initial_messages_content = ""
    from .tools import read_file # Import locally or ensure it's available
    
    context_errors = []

    for path in file_paths:
        # Use the safe read_file tool which enforces workspace limits
        content = read_file(path)
        if content.startswith("Error"):
             # If read failed, we track the error and ABORT later to notify Manager
             context_errors.append(f"Failed to read {path}: {content}")
        else:
             initial_messages_content += f"\n--- FILE: {os.path.basename(path)} ---\n{content}\n"

    if context_errors:
        # Return error to Manager immediately
        error_msg = "Context Loading Failed. The following paths were invalid or inaccessible:\n" + "\n".join(context_errors)
        print(json.dumps({"result": error_msg, "error": error_msg})) 
        return

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
    When finished, output 'DONE'.
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
    
    # Dirty Hack: Redirect stdout to stderr for the duration of the agent run
    # to protect the final JSON output from any rogue print statements in agent/libraries.
    original_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    try:
        final_status = agent.run_loop(max_steps=20) 
        last_message = agent.messages[-1].content
    except Exception as e:
        last_message = f"Error: {str(e)}"
        logging.error(f"Agent Loop Error: {e}")

    # Restore stdout
    sys.stdout = original_stdout
    
    # Output Result
    print(json.dumps({"result": last_message}))

if __name__ == "__main__":
    main()
