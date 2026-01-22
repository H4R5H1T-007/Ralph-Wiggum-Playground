import json
import os
from typing import Dict, Any, List
from langchain_core.messages import messages_to_dict, messages_from_dict, BaseMessage
from state import AgentState

STATE_FILE = ".state.json"

def save_state(state: AgentState, filepath: str = STATE_FILE):
    """Saves the AgentState to a JSON file."""
    
    # storage_dict = state.copy() # Shallow copy
    # We need to serialize messages
    
    serializable_state = {
        "messages": messages_to_dict(state["messages"]),
        "plan": state.get("plan", ""),
        "pending_tasks": state.get("pending_tasks", []),
        "results": state.get("results", {}), # Results might be complex? Assuming JSON serializable for now
        "iteration": state.get("iteration", 0)
    }
    
    with open(filepath, "w") as f:
        json.dump(serializable_state, f, indent=2)

def load_state(filepath: str = STATE_FILE) -> AgentState:
    """Loads the AgentState from a JSON file."""
    if not os.path.exists(filepath):
        return None
        
    with open(filepath, "r") as f:
        data = json.load(f)
        
    # Reconstruct messages
    if "messages" in data:
        data["messages"] = messages_from_dict(data["messages"])
        
    return data
