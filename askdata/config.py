
"""Configuration loaded from environment / .env for the AskData prototype."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Google Gemini configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
MODEL_NAME = os.environ.get("ASKDATA_MODEL", "gemini-2.5-flash")

DB_PATH = str(PROJECT_ROOT / os.environ.get("ASKDATA_DB_PATH", "askdata.db"))
SEMANTIC_LAYER_PATH = str(PROJECT_ROOT / "semantic_layer.yaml")

# No Gemini API key -> use the existing offline demo
OFFLINE_MODE = not bool(GEMINI_API_KEY)

MAX_SELF_CORRECTION_RETRIES = 2
DEFAULT_ROW_LIMIT = 500
