import json
import logging
from openai import OpenAI
from termcolor import colored
from .tools import TOOL_FUNCTIONS
from .tool_manager import ToolManager

class RalphAgent:
    def __init__(self, client: OpenAI, model: str, system_prompt: str, tools: list, name: str = "Ralph"):
        self.client = client
        self.model = model
        self.tools = tools
        self.name = name
        self.logger = logging.getLogger(name)
        self.tool_manager = ToolManager(logger_name=f"{name}.ToolManager")
        
        # Dynamic Tool Manifest
        tool_manifest = self._generate_tool_manifest(tools)
        full_system_prompt = f"{system_prompt}\n\n## AVAILABLE TOOLS\n{tool_manifest}"
        
        self.messages = [{"role": "system", "content": full_system_prompt}]

    def _generate_tool_manifest(self, tools: list) -> str:
        if not tools:
            return "No tools available."
        
        manifest = []
        for tool in tools:
            fn = tool.get("function", {})
            name = fn.get("name", "Unknown")
            desc = fn.get("description", "No description")
            params = fn.get("parameters", {}).get("properties", {})
            
            param_str = []
            for p_name, p_attrs in params.items():
                p_desc = p_attrs.get("description", "")
                param_str.append(f"  - `{p_name}`: {p_desc}")
            
            manifest.append(f"### {name}\n{desc}")
            if param_str:
                manifest.append("Arguments:\n" + "\n".join(param_str))
            
        return "\n\n".join(manifest)

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

        # Delegate execution to ToolManager (Parallel)
        tool_outputs = self.tool_manager.execute_tool_calls(message.tool_calls)
        
        # Append results to history and check for exit signals
        for output in tool_outputs:
            self.messages.append({
                "role": "tool",
                "tool_call_id": output["tool_call_id"],
                "content": output["content"]
            })
            
            # Check for Git Commit Signal
            if output["name"] == "git_commit":
                # If ANY tool was a git commit, we signal done. 
                # (Assuming nice behavior where commit is the final action)
                return "GIT_COMMIT_SIGNAL"

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
