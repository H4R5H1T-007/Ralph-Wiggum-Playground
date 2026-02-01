import os
import subprocess
import requests
from langchain_core.tools import tool
from config import WORKSPACE_DIR, CONTEXT7_API_KEY
from logger import logger

from functools import wraps

class ToolError(Exception):
    pass

def log_tool_usage(func):
    """Decorator to log tool calls and results."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.name if hasattr(func, 'name') else func.__name__
        try:
            logger.info(f"🔧 Tool Call: {tool_name} | Args: {args} {kwargs}")
            result = func(*args, **kwargs)
            logger.info(f"✅ Tool Result: {tool_name} | Output: {str(result)[:500]}...") # Truncate long output
            return result
        except Exception as e:
            logger.error(f"❌ Tool Error: {tool_name} | Error: {e}")
            raise e
    return wrapper

def validate_path(path: str) -> str:
    """Ensures path is within WORKSPACE_DIR. Resolves relative paths."""
    if not os.path.isabs(path):
        abs_path = os.path.abspath(os.path.join(WORKSPACE_DIR, path))
    else:
        abs_path = os.path.abspath(path)
    
    # Check if path is strictly inside workspace
    if not abs_path.startswith(os.path.abspath(WORKSPACE_DIR)):
        logger.warning(f"Access Denied: usage restricted to workspace ({WORKSPACE_DIR}). Path: {path}")
        raise ToolError(f"Access Denied: usage restricted to workspace ({WORKSPACE_DIR}). Path: {path}")
    return abs_path

@tool
@log_tool_usage
def read_file(path: str) -> str:
    """Read content of a file from the workspace."""
    try:
        safe_path = validate_path(path)
        if os.path.isdir(safe_path):
            return f"Error: '{path}' is a directory. Use list_dir instead."
            
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
            # logging handled by decorator now, but specific logic can stay if needed, 
            # though decorator covers it.
            return content
    except Exception as e:
        # Error logging handled by decorator or we can return string error
        # The tool usually returns string errors to LLM not raises exception
        return f"Error reading file: {e}"

@tool
@log_tool_usage
def write_file(path: str, content: str, mode: str = "overwrite") -> str:
    """
    Write content to a file in the workspace.

    Args:
        path: Path to the file.
        content: Content to write.
        mode: Write mode. Options: 'overwrite' (default) - replaces entire file, 'append' - adds to end of file.
    """
    try:
        safe_path = validate_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        if mode not in ["overwrite", "append"]:
            return f"Error: Invalid mode '{mode}'. Use 'overwrite' or 'append'."
            
        file_mode = "w" if mode == "overwrite" else "a"
        
        with open(safe_path, file_mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path} (mode={mode})"
    except Exception as e:
        return f"Error writing file: {e}"

@tool
@log_tool_usage
def list_dir(path: str) -> str:
    """List files in a directory within the workspace."""
    try:
        safe_path = validate_path(path)
        return str(os.listdir(safe_path))
    except Exception as e:
        return f"Error listing directory: {e}"

@tool
@log_tool_usage
def run_command(command: str, timeout: int = 120, background: bool = False) -> str:
    """
    Run a shell command inside the persistent 'ralph-workspace' container.
    
    Args:
        command: The shell command to execute.
        timeout: Maximum time in seconds to wait for the command (default: 120).
                 If a command takes longer, increase this value or break the work into smaller steps.
        background: If True, run command in detached mode (fire and forget). 
                    Useful for starting servers (e.g., 'npm run dev'). 
                    No output will be captured.

    Returns:
        Command output (STDOUT + STDERR) or status message.
    """
    try:
        # We assume the container 'ralph-workspace' is running.
        
        docker_args = ["docker", "exec", "-w", WORKSPACE_DIR]
        
        if background:
            docker_args.append("-d")
        
        docker_args.extend(["ralph-workspace", "/bin/sh", "-c", command])
        
        if background:
            subprocess.run(docker_args, check=True)
            return f"Command started in background: {command}"
        
        result = subprocess.run(docker_args, capture_output=True, text=True, timeout=timeout)
        
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
             output += f"\nExit Code: {result.returncode}"
        return output
        
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds. Consider increasing the timeout or breaking the task into smaller steps."
    except Exception as e:
        return f"Docker Execution Error: {e}"

@tool
@log_tool_usage
def git_commit(message: str) -> str:
    """Commit changes to git inside the workspace (running locally on host)."""
    try:
        # Validate workspace
        if not os.path.isdir(WORKSPACE_DIR):
             return f"Error: Workspace directory '{WORKSPACE_DIR}' does not exist."

        # Stage all
        # We run git commands directly in the WORKSPACE_DIR
        add_cmd = ["git", "add", "-A"]
        subprocess.run(add_cmd, cwd=WORKSPACE_DIR, check=True, capture_output=True)

        # Commit
        commit_cmd = ["git", "commit", "-m", message]
        
        result = subprocess.run(commit_cmd, cwd=WORKSPACE_DIR, capture_output=True, text=True)
        
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
             output += f"\nExit Code: {result.returncode}"
        return output

    except subprocess.CalledProcessError as e:
        return f"Git Error (Add/Commit failed): {e}"
    except Exception as e:
        return f"Git Execution Error: {e}"

@tool
@log_tool_usage
def context7_tool(query: str, library_name: str) -> str:
    """
    Fetch up-to-date documentation using Context7.
    
    Args:
        query: The specific question or feature to look up (e.g. "connection string format", "how to use actions").
        library_name: The name of the library (e.g. "prisma", "react", "next.js").
    
    Returns:
        Relevant documentation snippets.
    """
    try:
        headers = {}
        if CONTEXT7_API_KEY:
            headers["Authorization"] = f"Bearer {CONTEXT7_API_KEY}"
            
        # Step 1: Search for valid library ID
        search_url = "https://context7.com/api/v2/libs/search"
        search_params = {"libraryName": library_name, "query": query}
        
        search_response = requests.get(search_url, headers=headers, params=search_params)
        search_response.raise_for_status()
        
        search_data = search_response.json()
        libraries = search_data.get("results", []) if isinstance(search_data, dict) else search_data
        
        if not libraries:
            return f"Context7: No library found for '{library_name}'."
            
        # Use top match
        best_match = libraries[0]
        library_id = best_match.get("id")
        library_real_name = best_match.get("title")
        
        if not library_id:
             return f"Context7: Invalid library data found for '{library_name}'."

        # Step 2: Get Context
        context_url = "https://context7.com/api/v2/context"
        context_params = {
            "libraryId": library_id,
            "query": query,
            "type": "json" 
        }
        
        context_response = requests.get(context_url, headers=headers, params=context_params)
        context_response.raise_for_status()
        
        c_data = context_response.json()
        
        code_snippets = c_data.get("codeSnippets", [])
        info_snippets = c_data.get("infoSnippets", [])
        
        if not code_snippets and not info_snippets:
            return f"Context7: Found library '{library_real_name}' but no documentation returned for query '{query}'."
            
        output = [f"--- Context7 Results for '{library_real_name}' ---"]
        
        for snippet in code_snippets:
            title = snippet.get("codeTitle", "Untitled")
            desc = snippet.get("codeDescription", "")
            output.append(f"\nTitle: {title}\nDescription: {desc}")
            
            code_list = snippet.get("codeList", [])
            for code_item in code_list:
                lang = code_item.get("language", "")
                code = code_item.get("code", "")
                output.append(f"Code ({lang}):\n{code}")
        
        for snippet in info_snippets:
             title = snippet.get("title", "Untitled")
             content = snippet.get("content", "")
             output.append(f"\nTitle: {title}\nContent: {content}")
             
        return "\n".join(output)

    except Exception as e:
        return f"Context7 Error: {e}"
