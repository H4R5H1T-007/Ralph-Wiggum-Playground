import json
import logging
import tiktoken
from typing import List, Annotated, Literal, Any, Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from pydantic import BaseModel, Field

from config import RALPH_MODEL, SUBAGENT_MODEL, OPENROUTER_API_KEY, PROMPTS_DIR, WORKSPACE_DIR
from tools import read_file, list_dir, write_file, run_command, git_commit, context7_tool
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

TOKEN_LIMIT = 30000

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

def create_research_agent():
    """Creates a ReAct agent for research using Context7."""
    tools = [context7_tool]
    return create_react_agent(subagent_llm, tools)

research_agent = create_research_agent()

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

class DelegateResearch(BaseModel):
    """Delegate research tasks to the Research Agent using Context7."""
    query: str = Field(description="The specific question or feature to look up (e.g. 'connection string format', 'how to use actions').")
    library_name: str = Field(description="The name of the library (e.g. 'prisma', 'react', 'next.js').")

# Manager retains git_commit directly
manager_tools = [git_commit, PlanTasks, DelegateCommand, DelegateAdmin, DelegateResearch]
manager_llm_with_tools = llm.bind_tools(manager_tools)

# --- NODES ---

def manager_node(state: AgentState):
    """The Manager reasoning node."""
    messages = state["messages"]
    logger.info("Manager is thinking...")
    
    # Token Limit Safeguard
    try:
        enc = tiktoken.encoding_for_model("gpt-4")
        all_text = "".join([msg.content for msg in messages])
        token_count = len(enc.encode(all_text))
        
        if token_count > TOKEN_LIMIT:
            logger.warning(f"⚠️ Token Limit Reached ({token_count} > {TOKEN_LIMIT}). Injecting wrap-up instruction.")
            instruction = (
                f"SYSTEM ALERT: Context token limit ({TOKEN_LIMIT}) reached. "
                "You MUST wrap up immediately to avoid crashing. "
                "1. Mark the current task as done in @IMPLEMENTATION_PLAN.md (if partially done, note that). "
                "2. Update AGENTS.md with any learnings. "
                "3. Call `git_commit` with a detailed message describing what was accomplished in this session + ' (token limit reached)'. "
                "Do NOT start new tasks or ask for more details. Just save and exit."
            )
            # Append this as a SystemMessage to the end of the conversation for this turn only
            # Note: This modifies the list passed to invoke, but doesn't persist it unless we return it (which we won't, we return the response)
            # However, we want the MODEL to see it.
            messages = list(messages) + [SystemMessage(content=instruction)]
    except Exception as e:
        logger.error(f"Token count failed: {e}")

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

def research_node(state: dict):
    """Executes research tasks via ResearchAgent."""
    query = state["query"]
    lib = state["library_name"]
    sys_prompt = (
        "You are an expert Research Agent. Your goal is to find precise technical documentation using Context7. "
        "When calling context7_tool, optimize the 'query' argument to be specific and technical "
        "(e.g., use 'prisma client crud operations' instead of 'actions', or 'nextjs app router redirection' instead of 'how to move pages'). "
        "Context7 search works best with specific technical keywords. "
        "Analyze the request and refine the search query if necessary to get the most relevant technical documentation."
    )
    inputs = {"messages": [SystemMessage(content=sys_prompt), HumanMessage(content=f"Find info on '{query}' for library '{lib}'")]}
    try:
        result = research_agent.invoke(inputs)
        output = result["messages"][-1].content
        return {"results": {state["tool_call_id"]: output}}
    except Exception as e:
        return {"results": {state["tool_call_id"]: f"Research Failed: {e}"}}

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
    
    tasks, admin_tasks, cmd_task, research_tasks = [], [], None, []
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
        elif name == "DelegateResearch":
            research_tasks.append({"query": args.get("query"), "library_name": args.get("library_name"), "tool_call_id": tid})
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
    if research_tasks: updates["research_queue"] = research_tasks
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
    if state.get("research_queue"):
        dests.extend([Send("research", t) for t in state["research_queue"]])
        
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
    return {"messages": new_msgs, "pending_tasks": [], "admin_queue": [], "command_queue": None, "research_queue": []}
