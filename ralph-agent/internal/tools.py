import os
import json
import subprocess
import config  # Assumes config.py is in the parent directory (ralph-agent/) but we are in internal/. 
# We need to fix imports or path. Since we run from root, `import config` works if pythonpath is set.
# But better to use relative imports if possible, or assume running as module.
# Let's assume the main script sets up sys.path or we run from root.

# For now, let's just re-import config logic or rely on passing config. 
# Actually, tools.py will likely be imported by main.py in the root, so `import config` should work if running from root.

from config import WORKSPACE_DIR, INTERNAL_DIR, PROMPTS_DIR, OPENROUTER_API_KEY, SUBAGENT_MODEL

class ToolError(Exception):
    pass

def validate_path(path: str, allow_read_only=False):
    """Ensures path is within WORKSPACE_DIR."""
    abs_path = os.path.abspath(path)
    if allow_read_only and (abs_path.startswith(INTERNAL_DIR) or abs_path.startswith(PROMPTS_DIR)):
         # Internal/Prompts are strictly read-only, but logic elsewhere enforces WRITE restrictions.
         # For READ, we allow reading workspace. Reading internal? Maybe unsafe for the agent to read its own source?
         # Let's STRICTLY restrict to Workspace for now, as per plan.
         pass
    
    if not abs_path.startswith(os.path.abspath(WORKSPACE_DIR)):
        raise ToolError(f"Access Denied: usage restricted to workspace/ directory. Path: {path}")
    return abs_path

# --- File System Tools ---

def read_file(path: str):
    try:
        # We allow reading config/prompts if necessary? No, plan said workspace only strictly.
        # But wait, main.py reads prompts. The AGENT (LLM) should only read workspace.
        safe_path = validate_path(path)
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path: str, content: str):
    try:
        safe_path = validate_path(path)
        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

def list_dir(path: str):
    try:
        safe_path = validate_path(path)
        return str(os.listdir(safe_path))
    except Exception as e:
        return f"Error listing directory: {e}"

# --- Execution Tools ---

def run_command(command: str):
    """
    Executes a command inside the persistent 'ralph-workspace' container.
    Users 'docker exec' to ensure state persistence (e.g. installed packages).
    """
    try:
        # Construct Docker Exec command
        # Interactive mode (-it) might be tricky for automation, so we use non-interactive
        docker_cmd = [
            "docker", "exec", 
            "-w", "/app",
            "ralph-workspace", 
            "/bin/sh", "-c", command
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=120)
        
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
             output += f"\nExit Code: {result.returncode}"
        return output
    except Exception as e:
        return f"Docker Execution Error: {e}"

# --- Subagent Tools ---

def _run_subagent_process(instructions, file_paths):
    """Internal helper to run worker process."""
    worker_path = os.path.join(INTERNAL_DIR, "subagent_worker.py")
    
    # Validate file paths (subagents should also strictly read from workspace)
    safe_paths = []
    for p in file_paths:
        try:
            safe_paths.append(validate_path(p))
        except Exception:
            # If a path is invalid, we just skip it or warn?
            # Let's fail safe.
            return f"Error: Subagent file path out of bounds: {p}"

    payload = {
        "api_key": OPENROUTER_API_KEY,
        "model": SUBAGENT_MODEL,
        "instructions": instructions,
        "file_paths": safe_paths
    }

    try:
        process = subprocess.Popen(
            ["python3", worker_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=json.dumps(payload))
        
        if stderr:
            # Worker might print unexpected stderr (like 'using device cpu'), so we check stdout for result
            pass

        try:
            result_json = json.loads(stdout)
            if "error" in result_json:
                return f"Subagent Error: {result_json['error']}"
            return result_json.get("result", "No response from subagent.")
        except json.JSONDecodeError:
            return f"Subagent Failure. Output: {stdout} | Error: {stderr}"
            
    except Exception as e:
        return f"Subagent Process Error: {e}"

def study_specs(spec_paths: list[str], focus_question: str):
    instructions = f"""
    You are a Lead QA Analyst. 
    Your goal is to understand the requirements from the provided specifications.
    
    Focus Question: {focus_question}
    
    Analyze the attached spec files deeply. 
    Return a clear, concise summary answering the focus question.
    """
    return _run_subagent_process(instructions, spec_paths)

def study_code(file_paths: list[str], query: str):
    instructions = f"""
    You are a Senior Software Engineer.
    
    Query: {query}
    
    Analyze the attached source code files.
    Explain the logic, structure, or answer the specific query provided.
    """
    return _run_subagent_process(instructions, file_paths)

def delegate_subagent(instructions: str, file_paths: list[str]):
    return _run_subagent_process(instructions, file_paths)
