import os
import json
import subprocess
import uuid
import logging
from config import WORKSPACE_DIR, INTERNAL_DIR, PROMPTS_DIR, OPENROUTER_API_KEY, SUBAGENT_MODEL

class ToolError(Exception):
    pass

def validate_path(path: str, allow_read_only=False):
    """Ensures path is within WORKSPACE_DIR. Resolves relative paths against WORKSPACE_DIR."""
    if not os.path.isabs(path):
        abs_path = os.path.abspath(os.path.join(WORKSPACE_DIR, path))
    else:
        abs_path = os.path.abspath(path)

    if allow_read_only and (abs_path.startswith(INTERNAL_DIR) or abs_path.startswith(PROMPTS_DIR)):
         # Internal/Prompts are strictly read-only
         pass
    
    if not abs_path.startswith(os.path.abspath(WORKSPACE_DIR)):
        raise ToolError(f"Access Denied: usage restricted to configured workspace directory ({WORKSPACE_DIR}). Path: {path}")
    return abs_path

# --- Implementations ---

def read_file(path: str):
    try:
        safe_path = validate_path(path)
        
        # Check if it's a directory
        if os.path.isdir(safe_path):
            dir_contents = list_dir(path)
            return f"Error: '{path}' is a directory, not a file. Implementation: {dir_contents}"
            
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path: str, content: str):
    try:
        safe_path = validate_path(path)
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

def run_command(command: str):
    """Executes a command inside the persistent 'ralph-workspace' container."""
    try:
        # Log command
        try:
             safe_cmd_str = command.replace("'", "'\\''")
             log_cmd = ["docker", "exec", "ralph-workspace", "sh", "-c", f"echo '{safe_cmd_str}' >> {WORKSPACE_DIR}/command_history.log"]
             subprocess.run(log_cmd, check=False)
        except Exception:
             pass 

        # Execute
        docker_cmd = [
            "docker", "exec", 
            "-w", WORKSPACE_DIR,
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

def git_commit(message: str):
    try:
        add_cmd = ["docker", "exec", "-w", WORKSPACE_DIR, "ralph-workspace", "/bin/sh", "-c", "git add -A"]
        subprocess.run(add_cmd, check=True, capture_output=True)

        safe_message = message.replace('"', '\\"')
        commit_cmd = ["docker", "exec", "-w", WORKSPACE_DIR, "ralph-workspace", "/bin/sh", "-c", f'git commit -m "{safe_message}"']
        
        result = subprocess.run(commit_cmd, capture_output=True, text=True)
        
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
             output += f"\nExit Code: {result.returncode}"
        return output

    except subprocess.CalledProcessError as e:
        return f"Git Error (Add/Commit failed): {e}"
    except Exception as e:
        return f"Git Execution Error: {e}"

def _run_subagent_process(instructions, file_paths):
    """Internal helper to run worker process."""
    worker_path = os.path.join(INTERNAL_DIR, "subagent_worker.py")
    subagent_id = str(uuid.uuid4())[:8] # Short ID
    
    safe_paths = []
    for p in file_paths:
        try:
            safe_paths.append(validate_path(p, allow_read_only=True)) 
        except Exception:
             continue 

    payload = {
        "api_key": OPENROUTER_API_KEY,
        "model": SUBAGENT_MODEL,
        "instructions": instructions,
        "file_paths": safe_paths,
        "subagent_id": subagent_id
    }

    # Run as a module (python3 -m internal.subagent_worker) to resolve relative imports
    # We assume CWD is the root 'ralph-agent' directory, which is standard for main.py execution.
    try:
        logging.info(f"[{subagent_id}] Spawning Subagent...")
        
        process = subprocess.Popen(
            ["python3", "-m", "internal.subagent_worker"],
            cwd=os.path.dirname(INTERNAL_DIR), # Ensure we run from the parent of 'internal' (i.e., root)
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=json.dumps(payload))
        
        # Capture and log stderr from subagent
        if stderr:
            for line in stderr.splitlines():
                if line.strip():
                    logging.info(f"[{subagent_id}] {line}")

        try:
            result_json = json.loads(stdout)
            if "error" in result_json:
                error_msg = result_json['error']
                logging.error(f"[{subagent_id}] Error: {error_msg}")
                return f"Subagent Error: {error_msg}"
            
            result_msg = result_json.get("result", "No response from subagent.")
            logging.info(f"[{subagent_id}] Finished successfully.")
            return result_msg
            
        except json.JSONDecodeError:
            error_details = f"Output: {stdout} | Error: {stderr}"
            logging.error(f"[{subagent_id}] JSON Decode Fail: {error_details}")
            return f"Subagent Failure. {error_details}"
            
    except Exception as e:
        logging.error(f"[{subagent_id}] Process Error: {e}")
        return f"Subagent Process Error: {e}"

def study_specs(spec_paths: list[str], focus_question: str):
    instructions = f"""
    You are a Lead QA Analyst. 
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


# --- Tool Definitions ---

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read content of a file from workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to file"}},
            "required": ["path"]
        }
    }
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file in workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    }
}

LIST_DIR_TOOL = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "List files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"]
        }
    }
}

RUN_COMMAND_TOOL = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "Run a shell command inside the persistent workspace container.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Command to run"}},
            "required": ["command"]
        }
    }
}

GIT_COMMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "git_commit",
        "description": "Commit changes to git. This signals the completion of your task.",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Commit message"}},
            "required": ["message"]
        }
    }
}

DELEGATE_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_subagent",
        "description": "Delegate a coding or analysis task to a subagent.",
        "parameters": {
            "type": "object",
            "properties": {
                "instructions": {"type": "string"},
                "file_paths": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["instructions"]
        }
    }
}

STUDY_SPECS_TOOL = {
    "type": "function",
    "function": {
        "name": "study_specs",
        "description": "Spawn subagent to analyze specs.",
        "parameters": {
            "type": "object",
            "properties": {
                "spec_paths": {"type": "array", "items": {"type": "string"}},
                "focus_question": {"type": "string"}
            },
            "required": ["spec_paths", "focus_question"]
        }
    }
}

STUDY_CODE_TOOL = {
    "type": "function",
    "function": {
        "name": "study_code",
        "description": "Analyze logic across multiple files efficiently.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_paths": {"type": "array", "items": {"type": "string"}},
                "query": {"type": "string"}
            },
            "required": ["file_paths", "query"]
        }
    }
}

# --- Exported Sets ---

COMMON_TOOLS = [READ_FILE_TOOL, LIST_DIR_TOOL]
AUTHOR_TOOLS = [WRITE_FILE_TOOL]
MANAGER_TOOLS = [RUN_COMMAND_TOOL, GIT_COMMIT_TOOL, DELEGATE_TOOL, STUDY_SPECS_TOOL, STUDY_CODE_TOOL]

TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "run_command": run_command,
    "git_commit": git_commit,
    "delegate_subagent": delegate_subagent,
    "study_specs": study_specs,
    "study_code": study_code
}
