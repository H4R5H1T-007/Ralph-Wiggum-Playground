import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY")

# Model Configuration
RALPH_MODEL = os.getenv("RALPH_MODEL", "google/gemini-flash-1.5")
SUBAGENT_MODEL = os.getenv("SUBAGENT_MODEL", RALPH_MODEL)

# Paths
# Base dir of THIS module (ralph_graph)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_abs_path(env_var, default):
    path = os.getenv(env_var, default)
    path = os.path.expanduser(path)
    return os.path.abspath(path)

# Important: We want to share the workspace and prompts with the legacy agent (sibling directory)
# Assumption: ralph_graph and ralph-agent are siblings.
LEGACY_AGENT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "ralph-agent"))

WORKSPACE_DIR = get_abs_path("RALPH_WORKSPACE_DIR", os.path.join(LEGACY_AGENT_DIR, "workspace"))
PROMPTS_DIR = get_abs_path("RALPH_PROMPTS_DIR", os.path.join(BASE_DIR, "prompts"))

# Ensure workspace exists
os.makedirs(WORKSPACE_DIR, exist_ok=True)
