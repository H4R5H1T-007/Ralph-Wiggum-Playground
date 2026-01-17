import os
import sys
import argparse
from openai import OpenAI
from termcolor import colored
import config
from .agent import RalphAgent
from .tools import COMMON_TOOLS, AUTHOR_TOOLS, MANAGER_TOOLS
import logging

# Configure Logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "ralph.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a"
)

def main():
    parser = argparse.ArgumentParser(description="Ralph Agent Main Loop")
    parser.add_argument("mode", choices=["plan", "build"], help="Mode to run: plan or build")
    args = parser.parse_args()

    # Load Prompt
    prompt_file = os.path.join(config.PROMPTS_DIR, f"{args.mode}.md")
    try:
        with open(prompt_file, "r") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        print(colored(f"Error: Prompt file not found: {prompt_file}", "red"))
        sys.exit(1)

    print(colored(f"Starting Ralph in {args.mode.upper()} mode...", "green"))

    # Initialize Client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.OPENROUTER_API_KEY,
    )

    # Combine Tools: Manager gets EVERYTHING
    ALL_TOOLS = COMMON_TOOLS + AUTHOR_TOOLS + MANAGER_TOOLS

    agent = RalphAgent(
        client=client,
        model=config.RALPH_MODEL,
        system_prompt=system_prompt,
        tools=ALL_TOOLS,
        name="Ralph(Manager)"
    )

    # Load AGENTS.md (Operational Memory)
    agents_file = os.path.join(config.WORKSPACE_DIR, "AGENTS.md")
    if os.path.exists(agents_file):
        try:
            with open(agents_file, "r") as f:
                agents_content = f.read()
            if agents_content.strip():
                agent.add_message("user", f"Here is the content of @AGENTS.md. Use this to guide your operations:\n\n{agents_content}")
                print(colored("Loaded AGENTS.md context.", "blue"))
        except Exception as e:
            print(colored(f"Error loading AGENTS.md: {e}", "red"))

    # Run Loop
    exit_status = agent.run_loop(max_steps=100)
    
    # If the helper returns "DONE" via git commit, we exit 0 to restart.
    if exit_status == "DONE":
        sys.exit(0)
    else:
        # If loop finished without commit, we just exit.
        print(colored(f"Loop ended with status: {exit_status}", "yellow"))
        sys.exit(0)

if __name__ == "__main__":
    main()
