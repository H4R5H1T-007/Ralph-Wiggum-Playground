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

# --- WORKER SUB-AGENTS ---

def create_worker_agent():
    """Creates a ReAct agent for the worker."""
    tools = [read_file, write_file, list_dir]
    return create_react_agent(subagent_llm, tools)

worker_agent = create_worker_agent()

def create_command_agent():
    """Creates a ReAct agent for running commands."""
    tools = [run_command]
    return create_react_agent(subagent_llm, tools)

command_agent = create_command_agent()

def create_admin_agent():
    """Creates a ReAct agent for admin tasks."""
    tools = [read_file, write_file, list_dir]
    return create_react_agent(subagent_llm, tools)

admin_agent = create_admin_agent()

# --- MANAGER TOOLS ---

class PlanTasks(BaseModel):
    """Delegate heavy lifting coding tasks to subordinate workers."""
    tasks: List[WorkerTask] = Field(description="List of tasks to delegate")

class DelegateCommand(BaseModel):
    """Delegate a shell command execution to the Command Agent."""
    command: str = Field(description="The shell command to execute.")
    background: bool = Field(default=False, description="Run in background.")

class DelegateAdmin(BaseModel):
    """Delegate file/system admin tasks to the Admin Agent."""
    task_description: str = Field(description="Description of the admin task (e.g. 'read file X', 'list dir Y').")

# Manager retains git_commit directly
manager_tools = [git_commit, PlanTasks, DelegateCommand, DelegateAdmin]
manager_llm_with_tools = llm.bind_tools(manager_tools)

# --- NODES ---

def manager_node(state: AgentState):
    """The Manager reasoning node."""
    messages = state["messages"]
    logger.info("Manager is thinking...")
    response = manager_llm_with_tools.invoke(messages)
    return {"messages": [response]}

def worker_node(state: WorkerTask):
    """Executes a task assigned to a worker."""
    task_id = state["task_id"]
    description = state["description"]
    system_prompt = f"You are a Worker. GOAL: {description}. Use tools to read/write files."
    
    inputs = {"messages": [SystemMessage(content=system_prompt), HumanMessage(content="Start.")]}
    try:
        result = worker_agent.invoke(inputs)
        last_msg = result["messages"][-1].content
        return {"results": {task_id: f"Worker {task_id} Result: {last_msg}"}}
    except Exception as e:
        return {"results": {task_id: f"Worker {task_id} Failed: {e}"}}

def command_node(state: dict):
    """Executes a command via CommandAgent."""
    cmd = state["command"]
    sys_prompt = "You are a Command Agent. Execute the requested command using run_command."
    inputs = {"messages": [SystemMessage(content=sys_prompt), HumanMessage(content=f"Run: {cmd}")]}
    try:
        result = command_agent.invoke(inputs)
        output = result["messages"][-1].content
        return {"results": {state["tool_call_id"]: output}}
    except Exception as e:
        return {"results": {state["tool_call_id"]: f"Command Failed: {e}"}}

def admin_node(state: dict):
    """Executes admin tasks via AdminAgent."""
    desc = state["task_description"]
    sys_prompt = "You are an Admin Agent. Perform file/dir operations. NO commands."
    inputs = {"messages": [SystemMessage(content=sys_prompt), HumanMessage(content=desc)]}
    try:
        result = admin_agent.invoke(inputs)
        output = result["messages"][-1].content
        return {"results": {state["tool_call_id"]: output}}
    except Exception as e:
        return {"results": {state["tool_call_id"]: f"Admin Failed: {e}"}}

# --- DISPATCHER & LOGIC ---

def handle_plan_tasks(tc, args: dict, tasks: list):
    """Helper to parse PlanTasks."""
    raw_list = args.get("tasks", args.get("task_list", [args.get("task")]))
    if not isinstance(raw_list, list): raw_list = [raw_list]
    
    for i, item in enumerate(raw_list):
        t_id = f"{tc['id']}_{i}"
        desc = item if isinstance(item, str) else item.get("description", "Unknown")
        tasks.append({"task_id": t_id, "description": desc, "status": "pending"})

def dispatcher_node(state: AgentState):
    """Routes Manager tool calls."""
    last_message = state["messages"][-1]
    if not last_message.tool_calls: return {}
    
    tasks, admin_tasks, cmd_task = [], [], None
    local_results = {}
    
    for tc in last_message.tool_calls:
        name, args, tid = tc["name"], tc["args"], tc["id"]
        
        if name == "PlanTasks":
            handle_plan_tasks(tc, args, tasks)
        elif name == "DelegateCommand":
            # Singleton constraint: Only take the first command task
            if cmd_task is None:
                cmd_task = {"command": args.get("command"), "tool_call_id": tid}
            else:
                local_results[tid] = "Error: Only one Command Agent allowed per turn."
        elif name == "DelegateAdmin":
            admin_tasks.append({"task_description": args.get("task_description"), "tool_call_id": tid})
        elif name == "git_commit":
             # Execute locally
             try:
                 local_results[tid] = git_commit.invoke(args)
             except Exception as e:
                 local_results[tid] = f"Git Error: {e}"
        else:
             local_results[tid] = f"Error: Unknown tool {name}"

    # Flatten updates
    updates = {"results": local_results}
    if tasks: updates["pending_tasks"] = tasks
    if admin_tasks: updates["admin_queue"] = admin_tasks
    if cmd_task: updates["command_queue"] = cmd_task # Single item
    
    return updates

def should_continue(state: AgentState):
    """Decides next edge."""
    msg = state["messages"][-1]
    if not isinstance(msg, AIMessage) or not msg.tool_calls: return END
    return "dispatch"

def dispatch_logic(state: AgentState):
    """Routes execution."""
    dests = []
    if state.get("pending_tasks"):
        dests.extend([Send("worker", t) for t in state["pending_tasks"]])
    if state.get("admin_queue"):
        dests.extend([Send("admin", t) for t in state["admin_queue"]])
    if state.get("command_queue"):
        dests.append(Send("command", state["command_queue"]))
        
    return dests if dests else "reducer"

def reduce_node(state: AgentState):
    """Aggregates results."""
    results = state.get("results", {})
    last_msg = state["messages"][-1]
    new_msgs = []
    
    for tc in last_msg.tool_calls:
        tid = tc["id"]
        name = tc["name"]
        content = str(results.get(tid, f"No result for {name}"))
        
        if name == "PlanTasks":
            # Aggregate worker results
            p_tasks = state.get("pending_tasks", [])
            outputs = [str(results.get(t["task_id"], f"Task {t['task_id']} Pending")) for t in p_tasks]
            content = "\n\n".join(outputs)
            
        new_msgs.append(ToolMessage(content=content, tool_call_id=tid))
        
    # Clean up queues
    return {"messages": new_msgs, "pending_tasks": [], "admin_queue": [], "command_queue": None}
