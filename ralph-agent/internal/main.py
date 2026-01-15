import os
import sys
import json
import argparse
from openai import OpenAI
from termcolor import colored
import config
from .tools import (
    read_file, write_file, list_dir, run_command, 
    study_specs, study_code, delegate_subagent
)
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

# Tool Definitions for OpenAI API
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file from workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command inside the persistent workspace container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "study_specs",
            "description": "Spawn subagent to analyze specs. Use this to understand requirements before coding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec_paths": {"type": "array", "items": {"type": "string"}},
                    "focus_question": {"type": "string"}
                },
                "required": ["spec_paths", "focus_question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "study_code",
            "description": "Analyze logic across multiple files efficiently. Preferred over read_file for understanding code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string"}
                },
                "required": ["file_paths", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_subagent",
            "description": "Delegate ANY task (coding, reasoning, analysis) to a subagent to parallelize work. Use this often to save your own context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instructions": {"type": "string"},
                    "file_paths": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["instructions"]
            }
        }
    }
]

def execute_tool(tool_name, args):
    if tool_name == "read_file":
        return read_file(args["path"])
    elif tool_name == "write_file":
        return write_file(args["path"], args["content"])
    elif tool_name == "list_dir":
        return list_dir(args["path"])
    elif tool_name == "run_command":
        return run_command(args["command"])
    elif tool_name == "study_specs":
        return study_specs(args["spec_paths"], args["focus_question"])
    elif tool_name == "study_code":
        return study_code(args["file_paths"], args["query"])
    elif tool_name == "delegate_subagent":
        return delegate_subagent(args["instructions"], args.get("file_paths", []))
    else:
        return f"Unknown tool: {tool_name}"

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

    messages = [{"role": "system", "content": system_prompt}]
    
    # Load AGENTS.md (Operational Memory)
    agents_file = os.path.join(config.WORKSPACE_DIR, "AGENTS.md")
    if os.path.exists(agents_file):
        try:
            with open(agents_file, "r") as f:
                agents_content = f.read()
            if agents_content.strip():
                messages.append({
                    "role": "user", 
                    "content": f"Here is the content of @AGENTS.md. Use this to guide your operations (builds, tests, etc):\n\n{agents_content}"
                })
                print(colored("Loaded AGENTS.md context.", "blue"))
        except Exception as e:
            print(colored(f"Error loading AGENTS.md: {e}", "red"))

    # Loop
    step = 0
    MAX_STEPS = 100 # Safety limit
    
    while step < MAX_STEPS:
        step += 1
        print(colored(f"\n--- Step {step} ---", "blue"))
        
        try:
            completion = client.chat.completions.create(
                model=config.RALPH_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
        except Exception as e:
            print(colored(f"API Error: {e}", "red"))
            break

        message = completion.choices[0].message
        messages.append(message)

        if message.content:
            print(colored(f"Ralph: {message.content}", "cyan"))

        if message.tool_calls:
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                print(colored(f"Tool Call: {func_name}", "yellow"))
                
                # Execute
                try:
                    logging.info(f"Tool Call: {func_name} | Args: {func_args}")
                    result = execute_tool(func_name, func_args)
                    logging.info(f"Tool Result ({func_name}): {result}")
                except Exception as e:
                    error_msg = f"Error executing tool '{func_name}': {str(e)}"
                    logging.error(error_msg)
                    result = error_msg
                
                # Append result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })

                # CHECK FOR EXIT CONDITION:
                # If Ralph successfully committed/pushed code, his task is done.
                # We exit the process so loop.sh can restart him with clean context.
                if func_name == "run_command" and ("git commit" in func_args.get("command", "") or "git push" in func_args.get("command", "")):
                    print(colored("Task Completed (Commit/Push detected). Exiting loop for restart.", "green"))
                    sys.exit(0)
        else:
            # If no tool calls, Ralph is reporting back or done.
            # In Planning/Building mode, he effectively runs until he stops calling tools.
            # But usually he keeps going until he decides to stop.
            # For now, if no tool calls, we can assume he's waiting or done?
            # ReAct agents usually output "Final Answer". 
            # If he just speaks without tools, let's ask him to continue or stop.
            # But typically, if he outputs text without tool calls, that might be the end of the turn.
            if "IMPLEMENTATION_PLAN.md" in (message.content or "") and args.mode == "plan":
                 print(colored("Plan Updated. Exiting loop.", "green"))
                 break
            
            # Simple heuristic: If response is short and no tool, maybe just chat?
            # We'll continue unless he explicitly says "Done" or similar?
            # Actually, standard OpenAI loop stops if no tool calls.
            # But sometimes model explains then calls tool.
            # If `tool_calls` is None, checking if he wants to stop.
            pass
            
            # Check for stop condition?
            if "TASK COMPLETED" in (message.content or "").upper():
                 break
            
            # If purely text, we might want to prompt him to continue?
            # Or just break. Let's break if no tool calls, effectively "Turn Over".
            break

    print(colored("Loop Finished.", "green"))

if __name__ == "__main__":
    main()
