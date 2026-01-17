import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Warning: OPENROUTER_API_KEY not found in environment or .env file.")

# Model Configuration
RALPH_MODEL = os.getenv("RALPH_MODEL", "google/gemini-flash-1.5")
SUBAGENT_MODEL = os.getenv("SUBAGENT_MODEL", RALPH_MODEL)

# Agent Loop Limits
MAIN_AGENT_MAX_STEPS = int(os.getenv("RALPH_MAIN_MAX_STEPS", "200"))
SUBAGENT_MAX_STEPS = int(os.getenv("RALPH_SUBAGENT_MAX_STEPS", "100"))

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def get_abs_path(env_var, default):
    path = os.getenv(env_var, default)
    # Expand ~ to user home directory
    path = os.path.expanduser(path)
    # Convert to absolute path
    return os.path.abspath(path)

WORKSPACE_DIR = get_abs_path("RALPH_WORKSPACE_DIR", os.path.join(BASE_DIR, "workspace"))
PROMPTS_DIR = get_abs_path("RALPH_PROMPTS_DIR", os.path.join(BASE_DIR, "prompts"))
INTERNAL_DIR = os.path.join(BASE_DIR, "internal")

# Ensure critical directories exist
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(INTERNAL_DIR, exist_ok=True)
