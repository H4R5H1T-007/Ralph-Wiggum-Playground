import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from termcolor import colored
from .tools import TOOL_FUNCTIONS

# Helper function must be top-level to be picklable
def _execute_single_tool(func_name, args_str):
    try:
        args = json.loads(args_str)
        func = TOOL_FUNCTIONS.get(func_name)
        if not func:
            return f"Error: Unknown tool '{func_name}'"
        return func(**args)
    except json.JSONDecodeError:
        return "Error: Invalid JSON arguments"
    except Exception as e:
        return f"Error executing tool '{func_name}': {str(e)}"

class ToolManager:
    def __init__(self, logger_name="ToolManager"):
        self.logger = logging.getLogger(logger_name)
        # We can adjust max_workers if needed. Default is usually number of processors.
        self.executor = ProcessPoolExecutor()

    def execute_tool_calls(self, tool_calls):
        """
        Executes a list of OpenAI ToolCall objects in parallel (using processes).
        Returns a list of dictionaries:
        [
            {"tool_call_id": "...", "role": "tool", "content": "...", "name": "..."}
        ]
        """
        futures_map = {}
        results_data = []

        # 1. Submit all jobs
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args_str = tool_call.function.arguments
            
            print(colored(f"ToolManager queuing: {func_name}", "yellow"))
            self.logger.info(f"Tool Queued: {func_name} | Args: {func_args_str}")

            future = self.executor.submit(_execute_single_tool, func_name, func_args_str)
            futures_map[future] = tool_call

        # 2. Wait for results
        # We want to maintain order matching the input list for neatness? 
        # OpenAI doesn't strictly require order, but appending to history in order is nice.
        # However, as_completed yields as they finish.
        
        # We'll collect them in a dict keyed by tool_call.id then reassemble or just append.
        # Actually simplest is just to wait for all.
        
        completed_results = {}

        for future in as_completed(futures_map):
            tool_call = futures_map[future]
            try:
                result_str = future.result()
            except Exception as e:
                result_str = f"System Error executing tool: {e}"
            
            self.logger.info(f"Tool Finished ({tool_call.function.name}): {result_str}")
            completed_results[tool_call.id] = result_str

        # 3. Reassemble in original order
        final_output = []
        for tool_call in tool_calls:
            res_content = completed_results.get(tool_call.id, "Error: No result")
            final_output.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(res_content),
                "name": tool_call.function.name # Useful for logic checks
            })

        return final_output
