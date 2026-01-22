import json
import logging
from typing import List, Annotated, Literal, Any, Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from pydantic import BaseModel, Field

from config import RALPH_MODEL, SUBAGENT_MODEL, OPENROUTER_API_KEY, PROMPTS_DIR, WORKSPACE_DIR
from tools import read_file, list_dir, write_file, run_command, git_commit
from state import AgentState, WorkerTask
from logger import logger

# Initialize Models
llm = ChatOpenAI(
    model=RALPH_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

subagent_llm = ChatOpenAI(
    model=SUBAGENT_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# --- WORKER NODE (Subgraph) ---

def create_worker_agent():
    """Creates a ReAct agent for the worker."""
    tools = [read_file, write_file, list_dir]
    return create_react_agent(subagent_llm, tools)

worker_agent = create_worker_agent()

def worker_node(state: WorkerTask):
    """
    Executes a task assigned to a worker.
    """
    task_id = state["task_id"]
    description = state["description"]
    
    # Construct the system prompt for the worker
    system_prompt = f"""You are a Skilled Developer/Worker.
    INSTRUCTIONS:
    - Append your operational learnings into your response to manager. if that is not possible then append it into @AGENTS.md. If the file is not present, create it. Note this is being used by multiple agents so please try to avoid overwriting existing content. 
    - If you encounter any bugs during your work, document (append) them in @IMPLEMENTATION_PLAN.md as work items that need to be addressed. Do not attempt to fix them; simply add them to the plan.
    GOAL: {description}
    
    You have tools to READ and WRITE files.
    You DO NOT have tools to run commands or build the project.
    
    Perform the requested task.
    """
    
    inputs = {"messages": [SystemMessage(content=system_prompt), HumanMessage(content="Please start working.")]}
    
    try:
        # Run subgraph
        result = worker_agent.invoke(inputs)
        messages = result["messages"]
        last_msg = messages[-1].content if messages else "No output"
        logger.info(f"👷 Worker {task_id} finished.")
        
        # Return result mapped by task_id for the Reducer
        return {"results": {task_id: f"Worker {task_id} ({description}) Result: {last_msg}"}}
        
    except Exception as e:
        # Check for recursion error (including LangGraph's GraphRecursionError)
        if "RecursionError" in type(e).__name__ or "recursion" in str(e).lower():
             logger.warning(f"⚠️ Worker {task_id} hit recursion limit.")
             return {"results": {task_id: f"Worker {task_id} ({description}) Failed: Task too complex please break down the task"}}
        
        logger.error(f"❌ Worker {task_id} failed: {e}")
        return {"results": {task_id: f"Worker {task_id} Error: {e}"}}

# --- MANAGER NODE ---

manager_tools = [read_file, list_dir, run_command, git_commit]

class PlanTasks(BaseModel):
    """Call this to delegate tasks to subordinate workers."""
    tasks: List[WorkerTask] = Field(description="List of tasks to delegate")

manager_llm_with_tools = llm.bind_tools(manager_tools + [PlanTasks])

def manager_node(state: AgentState):
    """
    The Manager reasoning node.
    """
    messages = state["messages"]
    
    logger.info("Manager is thinking...")
    response = manager_llm_with_tools.invoke(messages)
    
    if response.tool_calls:
        for tc in response.tool_calls:
            logger.info(f"👉 Manager chose tool: {tc['name']} with args: {tc['args']}")
    else:
        logger.info(f"🗣️ Manager says: {response.content}")
    
    return {"messages": [response]}

# --- DISPATCHER NODE ---

def dispatcher_node(state: AgentState):
    """
    Handles Manager's tool calls.
    - Executes local tools immediately.
    - Queues Worker tasks.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    tasks = []
    local_results = {} 
    
    # Map name to function
    tool_map = {
        "read_file": read_file,
        "list_dir": list_dir,
        "write_file": write_file, # Not in manager tools above, but if added...
        "run_command": run_command,
        "git_commit": git_commit
    }

    if not last_message.tool_calls:
        return {}

    for tc in last_message.tool_calls:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        
        if name == "PlanTasks":
            if "tasks" in args:
                tasks.extend(args["tasks"])
            elif "task" in args:
                single_task = args["task"]
                if isinstance(single_task, str):
                    tasks.append({"task_id": "1", "description": single_task})
                elif isinstance(single_task, dict):
                    tasks.append(single_task)
            
            # We don't execute PlanTasks locally, we just queue content.
            # But strictly, we need to provide a result for this tool call eventually.
            # We'll let the Reducer handle the "PlanTasks" result generation.
            
        elif name in tool_map:
            logger.info(f"🛠️ Dispatcher executing local tool: {name}")
            try:
                tool_func = tool_map[name]
                # Assuming simple invocation works for our @tool definitions
                result = tool_func.invoke(args)
                local_results[tool_call_id] = result
            except Exception as e:
                local_results[tool_call_id] = f"Error executing {name}: {e}"
        else:
            local_results[tool_call_id] = f"Error: Unknown tool {name}"

    return {"pending_tasks": tasks, "results": local_results}

def should_continue(state: AgentState):
    """
    Determines next step after Manager.
    - If tool calls -> dispatch
    - Else -> END (Wait for user input or loop to restart? 
      Actually if Manager just speaks, we might want to end the turn).
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if not isinstance(last_message, AIMessage):
        return END
        
    if last_message.tool_calls:
        return "dispatch"
    
    return END

def dispatch_logic(state: AgentState):
    """
    Conditional edge after Dispatcher.
    - If tasks -> map to workers
    - Else -> reducer (to just process local results)
    """
    tasks = state.get("pending_tasks", [])
    if tasks:
        return [Send("worker", task) for task in tasks]
    return "reducer"

def reduce_node(state: AgentState):
    """
    Aggregates results from 'results' dict (populated by Dispatcher and Workers).
    Appends them to history as ToolMessages.
    """
    results = state.get("results", {})
    messages = state["messages"]
    last_message = messages[-1] # This should be the Manager's AIMessage with tool_calls
    
    new_messages = []
    
    # Iterate through tool calls to generate corresponding ToolMessages
    for tc in last_message.tool_calls:
        tool_call_id = tc["id"]
        name = tc["name"]
        
        if name == "PlanTasks":
            # Gather all results that look like task outputs
            pending_tasks = state.get("pending_tasks", [])
            task_outputs = []
            
            # Since workers report their results into `results` dict keyed by task_id?
            # Wait, worker_node returns { "results": { task_id: ... } }
            # So `state["results"]` should contain keys for task_id.
            
            for task in pending_tasks:
                tid = task.get("task_id")
                # Check if this task has a result
                if tid in results:
                     task_outputs.append(str(results[tid]))
                else:
                    # Provide a placeholder if failed or cancelled
                     task_outputs.append(f"Task {tid} ({task.get('description')}): No result found.")
            
            combined_output = "\n\n".join(task_outputs) if task_outputs else "No tasks were executed."
            new_messages.append(ToolMessage(content=combined_output, tool_call_id=tool_call_id))
            
        elif tool_call_id in results:
            # It's a local tool result
            new_messages.append(ToolMessage(content=str(results[tool_call_id]), tool_call_id=tool_call_id))
        else:
            # Missing result?
            new_messages.append(ToolMessage(content="Error: No result generated for this tool call.", tool_call_id=tool_call_id))
            
    # Return formatted messages to append to history
    return {"messages": new_messages}
