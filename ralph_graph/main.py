import os
import sys
from langchain_core.messages import SystemMessage, AIMessage
from termcolor import colored

# Add current dir to path to find local modules if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_graph
from config import PROMPTS_DIR
from logger import logger
from state_manager import load_state, save_state

def main():
    logger.info(colored("Initializing Ralph Graph Agent Loop...", "cyan"))
    
    # 1. Load or Initialize State
    state = load_state()
    
    if not state:
        logger.info("No existing state found. Starting fresh.")
        # Load Initial Prompt
        build_prompt_path = os.path.join(PROMPTS_DIR, "build.md")
        try:
            with open(build_prompt_path, "r") as f:
                build_prompt = f.read()
        except FileNotFoundError:
            logger.error(f"Error: Could not find build prompt at {build_prompt_path}")
            return

        state = {
            "messages": [SystemMessage(content=build_prompt)],
            "pending_tasks": [],
            "results": {},
            "iteration": 0
        }
    else:
        logger.info("Resuming from previous state.")

    # 2. Create the graph
    app = create_graph()
    
    # 3. Execution Loop
    try:
        while True:
            current_iter = state.get("iteration", 0)
            logger.info(colored(f"--- Iteration {current_iter + 1} ---", "blue"))
            
            # Run one pass of the DAG
            # invoke returns the final state of the graph
            result = app.invoke(state)
            
            # Validate result (Graph might return partial state updates, but StateGraph usually returns full state)
            state = result
            # state["iteration"] = current_iter + 1 # Iteration is updated in state, but we don't need to check it for termination
            
            # Save state - DISABLED per user request (State maintained in memory)
            # save_state(state)
            
            # Explicitly clear transient state for the next turn
            # This is crucial because standard graph merges might not clear old results if we don't have reducers for them.
            state["results"] = {}
            state["pending_tasks"] = []
            
            # Check for termination condition: git_commit
            messages = state["messages"]
            if messages:
                last_msg = messages[-1]
                # Check for git_commit in ALL messages of this turn? 
                # Ideally, the Manager called it.
                # If Manager called it, it would be in the last AIMessage, 
                # OR in the history if we just finished a tool execution step.
                # Actually, our DAG ends after Dispatch/Tool Execution.
                # So if Manager called `git_commit`, the Dispatcher executed it.
                # The Dispatcher returned, loop ended.
                # So we verify if `git_commit` was in the executed tools.
                
                # We can check the last AIMessage for tool_calls with name 'git_commit'
                # And confirm we aren't waiting for results (DAG finished).
                
                # Scan backwards for the last AIMessage
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tc in msg.tool_calls:
                            if tc["name"] == "git_commit":
                                logger.info(colored("✅ 'git_commit' detected. Job Complete. Exiting Loop.", "green"))
                                return
                        break # Only check the most recent AI turn
            
            # Optional: Add a safety break (max iterations)
            # REMOVED per user request
            # if state["iteration"] > 50:
            #      logger.warning("Reached max iterations (50). Stopping.")
            #      break
                 
    except KeyboardInterrupt:
        logger.info("🛑 User interrupted execution.")
        save_state(state)
    except Exception as e:
        logger.error(f"❌ Loop Error: {e}")
        save_state(state)
        raise e

if __name__ == "__main__":
    main()
