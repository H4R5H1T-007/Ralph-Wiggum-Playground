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

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
INTERNAL_DIR = os.path.join(BASE_DIR, "internal")

# Ensure critical directories exist
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(INTERNAL_DIR, exist_ok=True)
