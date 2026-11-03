"""Application configuration for LocalGPT.

Every value can be overridden with an environment variable so that the
application stays configurable without editing source code.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = Path(os.environ.get("LOCALGPT_DB", DATABASE_DIR / "localgpt.db"))

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = os.environ.get("LOCALGPT_HOST", "127.0.0.1")
PORT = int(os.environ.get("LOCALGPT_PORT", "5000"))
DEBUG = os.environ.get("LOCALGPT_DEBUG", "0") == "1"

# ---------------------------------------------------------------------------
# Ollama (local only)
# ---------------------------------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("LOCALGPT_MODEL", "llama3.2:3b")

# Connection timeout is short: a missing Ollama must fail fast.
OLLAMA_CONNECT_TIMEOUT = float(os.environ.get("LOCALGPT_CONNECT_TIMEOUT", "5"))
# Generation can take a while on CPU; allow a generous read timeout.
OLLAMA_READ_TIMEOUT = float(os.environ.get("LOCALGPT_READ_TIMEOUT", "300"))

# ---------------------------------------------------------------------------
# Model parameters (tuned for 16 GB RAM / RTX 3050 6 GB, but not forced)
# ---------------------------------------------------------------------------
# num_ctx is the total context window. 4096 keeps VRAM usage modest while
# still allowing long conversations; the prompt builder trims history to fit.
NUM_CTX = int(os.environ.get("LOCALGPT_NUM_CTX", "4096"))
NUM_PREDICT = int(os.environ.get("LOCALGPT_NUM_PREDICT", "1024"))
TEMPERATURE = float(os.environ.get("LOCALGPT_TEMPERATURE", "0.7"))
TOP_P = float(os.environ.get("LOCALGPT_TOP_P", "0.9"))
REPEAT_PENALTY = float(os.environ.get("LOCALGPT_REPEAT_PENALTY", "1.1"))
KEEP_ALIVE = os.environ.get("LOCALGPT_KEEP_ALIVE", "10m")

# ---------------------------------------------------------------------------
# Conversation limits
# ---------------------------------------------------------------------------
MAX_MESSAGE_CHARS = int(os.environ.get("LOCALGPT_MAX_MESSAGE_CHARS", "32000"))
MAX_TITLE_CHARS = 60
# Rough character budget for history. Tokens are estimated at ~4 chars/token.
# Reserve room for the reply and the system prompt.
CONTEXT_CHAR_BUDGET = max(1000, int((NUM_CTX - NUM_PREDICT - 256) * 3.5))

# ---------------------------------------------------------------------------
# Real-time awareness
# ---------------------------------------------------------------------------
TIMEZONE = os.environ.get("LOCALGPT_TIMEZONE", "Asia/Kolkata")
LOCATION = os.environ.get("LOCALGPT_LOCATION", "Pune, India")  # configurable
ENABLE_WEB_SEARCH = os.environ.get("LOCALGPT_ENABLE_WEB_SEARCH", "0") == "1"

SYSTEM_PROMPT = os.environ.get(
    "LOCALGPT_SYSTEM_PROMPT",
    "You are LocalGPT, a helpful, intelligent, and friendly personal AI "
    "assistant running entirely on the user's local computer.\n\n"
    "Your job is to answer questions, explain concepts, help with programming, "
    "assist with learning, and have natural conversations.\n\n"
    "Use clear language and structured answers.\n\n"
    "Adapt explanations to the user's knowledge level.\n\n"
    "Be honest when you do not know an answer.\n\n"
    "Remember the conversation context and use previous messages when "
    "answering follow-up questions.\n\n"
    "Never claim to have internet access or real-time information unless such "
    "functionality has explicitly been implemented.",
)

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
MAX_CONTENT_LENGTH = 1024 * 1024  # 1 MB request body cap
