from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.types import Send

from state import AgentState
from nodes import (
    manager_node, 
    manager_tools, 
    should_continue, 
    dispatcher_node,
    dispatch_logic, # conditional edge
    worker_node, 
    reduce_node
)

def create_graph():
    workflow = StateGraph(AgentState)
    
    # 1. Add Nodes
    workflow.add_node("manager", manager_node)
    workflow.add_node("dispatcher", dispatcher_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("reducer", reduce_node)
    
    # 2. Add Edges
    workflow.set_entry_point("manager")
    
    # Manager -> Dispatcher or END
    workflow.add_conditional_edges(
        "manager",
        should_continue,
        {
            "dispatch": "dispatcher",
            END: END
        }
    )
    
    # Dispatcher -> Worker (Map) or Reducer
    workflow.add_conditional_edges(
        "dispatcher", 
        dispatch_logic,
        ["worker", "reducer"] 
    )
    
    # Workers return to reducer
    workflow.add_edge("worker", "reducer")
    
    # Reducer returns to END (Loop handled by main.py)
    workflow.add_edge("reducer", END)
    
    return workflow.compile()
