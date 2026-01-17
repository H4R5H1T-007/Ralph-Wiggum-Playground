import os
import subprocess
import sys
from termcolor import colored
import config

def ensure_workspace_container():
    """
    Ensures the ralph-workspace container is running using docker-compose,
    with the correctly configured workspace directory.
    """
    print(colored("Checking Workspace Container...", "blue"))
    
    # We explicitly set the environment variable for the subprocess
    # This ensures docker-compose picks up the path from config.py
    env = os.environ.copy()
    env["RALPH_WORKSPACE_DIR"] = config.WORKSPACE_DIR
    
    try:
        # Run docker compose up -d
        # This command handles creation and recreation if configuration changes
        cmd = ["docker", "compose", "up", "-d", "ralph-workspace"]
        
        result = subprocess.run(
            cmd, 
            env=env, 
            cwd=config.BASE_DIR, # Run from project root
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            print(colored(f"Container 'ralph-workspace' is up. Workspace: {config.WORKSPACE_DIR}", "green"))
        else:
            print(colored(f"Error starting container:\n{result.stderr}", "red"))
            sys.exit(1)
            
    except Exception as e:
        print(colored(f"Exception managing container: {e}", "red"))
        sys.exit(1)

if __name__ == "__main__":
    ensure_workspace_container()
