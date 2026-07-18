"""Configuration for the HR Policy Agent (given — you don't need to edit this)."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Model ---------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# --- Retrieval brain: "okf" | "rag" | "hybrid" ---------------------------
# okf   -> traverse the local knowledge/ OKF bundle (no Google Cloud needed)
# rag   -> query Vertex AI Search (requires Track A setup in rag/)
# hybrid-> OKF first, RAG fallback (stretch exercise)
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "okf").lower()

# --- Paths ---------------------------------------------------------------
# Absolute path to the OKF bundle, resolved relative to the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(REPO_ROOT, "knowledge")

# --- Vertex AI Search (only used when RETRIEVAL_MODE includes rag) --------
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_AI_SEARCH_LOCATION = os.getenv("VERTEX_AI_SEARCH_LOCATION", "global")
VERTEX_AI_DATA_STORE_ID = os.getenv("VERTEX_AI_DATA_STORE_ID", "hr-policies-lab-store")
VERTEX_AI_SEARCH_ENGINE_ID = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID", "hr-policies-lab-engine")

APP_NAME = "hr_policy_lab"
