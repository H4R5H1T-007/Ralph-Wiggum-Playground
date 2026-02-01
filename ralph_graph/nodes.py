import sys
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
    base_url="https://openrouter.ai/api/v1",
    # This passes extra fields directly in the request body
    extra_body={
        "provider": {
            "only": ["chutes"],           # strict: only Chutes, fail if unavailable
            # OR use "order": ["chutes"]   # prefer Chutes first, fallback to others
            # OR "ignore": ["mistral"]     # skip official Mistral provider
        }
    },
    max_tokens=8192
)

subagent_llm = ChatOpenAI(
    model=SUBAGENT_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    # This passes extra fields directly in the request body
    extra_body={
        "provider": {
            "only": ["chutes"],           # strict: only Chutes, fail if unavailable
            # OR use "order": ["chutes"]   # prefer Chutes first, fallback to others
            # OR "ignore": ["mistral"]     # skip official Mistral provider
        }
    },
    max_tokens=8192
)

TOKEN_LIMIT = 20000
REMAINING_GRACE_TURNS = 5

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
    """
    Delegate research tasks to the Research Agent. 
    Use this tool when you need external documentation, or when a command/code fails and you need to investigate the error. 
    This tool effectively searches for official documentation and code examples to verify syntax, library usage, or fix bugs.
    """
    query: str = Field(description="The specific question or feature to look up (e.g. 'connection string format', 'how to use actions').")
    library_name: str = Field(description="The name of the library (e.g. 'prisma', 'react', 'next.js').")

# Manager retains git_commit directly
manager_tools = [git_commit, PlanTasks, DelegateCommand, DelegateAdmin, DelegateResearch]
manager_llm_with_tools = llm.bind_tools(manager_tools)

# --- NODES ---

def manager_node(state: AgentState):
    """The Manager reasoning node."""
    global REMAINING_GRACE_TURNS 
    messages = state["messages"]
    logger.info("Manager is thinking...")
    
    # Token Limit Safeguard
    try:
        enc = tiktoken.encoding_for_model("gpt-4")
        all_text = "".join([msg.content for msg in messages])
        token_count = len(enc.encode(all_text))
        
        if token_count > TOKEN_LIMIT:
            if REMAINING_GRACE_TURNS > 0:
                logger.warning(f"⚠️ Token Limit Reached ({token_count} > {TOKEN_LIMIT}). Grace turns remaining: {REMAINING_GRACE_TURNS}")
                instruction = (
                    f"SYSTEM ALERT: Context token limit ({TOKEN_LIMIT}) reached. "
                    f"You have {REMAINING_GRACE_TURNS} turns left before the process is forcibly terminated. "
                    "You MUST save your work NOW.\n"
                    "1. Update `@IMPLEMENTATION_PLAN.md` (mark tasks as partial/done).\n"
                    "2. Update `@AGENTS.md` with any key learnings.\n"
                    "3. Call `git_commit` immediately.\n"
                    "If you fail to do so, the system will force an auto-commit and exit, but your documentation updates may be lost. "
                    "Do not run any other tools (e.g. do not try to read files or run commands) because the process will exit before you can see their results."
                )
                
                # Fix for Strict Providers (Tool -> AI -> User sequence)
                injected_safeguard_msgs = []
                if messages:
                    last_msg = messages[-1]
                    if getattr(last_msg, "type", "") == "tool":
                         logger.info("Injecting dummy AI acknowledgment after ToolMessage to allow warning injection.")
                         injected_safeguard_msgs.append(AIMessage(content="Tool execution completed. Processing results."))

                # Changed to HumanMessage to avoid "Unexpected role 'system' after role 'tool'" errors
                # But now we ensure it's preceded by an AI message if needed
                injected_safeguard_msgs.append(HumanMessage(content=instruction))
                
                messages = list(messages) + injected_safeguard_msgs
                REMAINING_GRACE_TURNS -= 1
            else:
                logger.error(f"❌ Hard Token Limit Exceeded ({token_count}) and Grace Period Expired. Force Exit.")
                
                # Auto-Save Safety Net
                try:
                    logger.info("Performing Auto-Save before exit...")
                    git_commit.invoke({"message": "Auto-save: Hard token limit exceeded."})
                except Exception as save_err:
                    logger.error(f"Auto-save failed: {save_err}")
                
                sys.exit(0)
        else:
             # Reset grace turns if tokens drop below limit
             REMAINING_GRACE_TURNS = 5

    except Exception as e:
        logger.error(f"Token count failed: {e}")

    # Fix for Chutes/Strict Providers: Ensure history doesn't end with AIMessage
    injected_msgs = []
    if messages and isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls:
        logger.info("Injecting 'Continue' message to satisfy provider turn-taking.")
        cont_msg = HumanMessage(content="Continue.")
        messages = list(messages) + [cont_msg]
        injected_msgs.append(cont_msg)

    response = manager_llm_with_tools.invoke(messages)
    logger.info(f"Manager response: {response}")
    return {"messages": injected_msgs + [response]}

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
    sys_prompt = (
        "You are a Command Agent. Execute the requested command using `run_command`. "
        "If the command execution appears to hang or takes an excessive amount of time, "
        "return a final response stating that the command is taking too long and advise checking the code for issues."
    )
    inputs = {"messages": [SystemMessage(content=sys_prompt), HumanMessage(content=f"Run: {cmd}")]}
    try:
        result = command_agent.invoke(inputs)
        output = result["messages"][-1].content
        return {"results": {state["tool_call_id"]: output}}
    except Exception as e:
        return {"results": {state["tool_call_id"]: f"Command Failed: {e}\nSUGGESTION: Use `DelegateResearch` to investigate this error."}}

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
