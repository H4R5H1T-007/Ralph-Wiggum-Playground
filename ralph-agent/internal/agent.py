import json
import logging
from openai import OpenAI
from termcolor import colored
from .tools import TOOL_FUNCTIONS

class RalphAgent:
    def __init__(self, client: OpenAI, model: str, system_prompt: str, tools: list, name: str = "Ralph"):
        self.client = client
        self.model = model
        self.tools = tools
        self.name = name
        self.messages = [{"role": "system", "content": system_prompt}]
        self.logger = logging.getLogger(name)

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def step(self):
        """Execute one turn of the agent loop."""
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto" if self.tools else "none"
            )
        except Exception as e:
            self.logger.error(f"API Error: {e}")
            return f"API Error: {e}"

        message = completion.choices[0].message
        self.messages.append(message)

        if message.content:
            print(colored(f"{self.name}: {message.content}", "cyan"))

        if not message.tool_calls:
            return "No tool calls"

        results = []
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args_str = tool_call.function.arguments
            
            print(colored(f"{self.name} calls Tool: {func_name}", "yellow"))
            self.logger.info(f"Tool Call: {func_name} | Args: {func_args_str}")

            try:
                args = json.loads(func_args_str)
                func = TOOL_FUNCTIONS.get(func_name)
                
                if not func:
                    result = f"Error: Unknown tool '{func_name}'"
                else:
                    result = func(**args)
                
            except json.JSONDecodeError:
                result = "Error: Invalid JSON arguments"
            except Exception as e:
                result = f"Error executing tool '{func_name}': {str(e)}"
            
            self.logger.info(f"Tool Result ({func_name}): {result}")
            
            # Append result
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })
            
            # Special Handling for Git Commit (Exit Signal for Main Agent)
            if func_name == "git_commit":
                return "GIT_COMMIT_SIGNAL"
                
            results.append(result)

        return "Tool calls executed"

    def run_loop(self, max_steps=50):
        step = 0
        while step < max_steps:
            step += 1
            print(colored(f"\n--- {self.name} Turn {step} ---", "blue"))
            result = self.step()
            
            if result == "GIT_COMMIT_SIGNAL":
                print(colored("Task Completed (Git Commit).", "green"))
                return "DONE"
            
            if result == "No tool calls":
                # For Subagents (and maybe Main), if they stop calling tools, they might be done.
                # But we should check if they said "DONE" or just wrote text.
                # Simple heuristic: If tool list is present but unused, and message contains "DONE", exit.
                last_msg = self.messages[-1].content or ""
                if "DONE" in last_msg.upper() or "COMPLETED" in last_msg.upper():
                    return last_msg
                # Else continue? or Break? 
                # Better to break to avoid infinite loops of chatter.
                return last_msg
                
        return "Max steps reached"
