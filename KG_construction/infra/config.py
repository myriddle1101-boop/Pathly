from pathlib import Path
import os

try:
    from env_loader import load_project_env

    load_project_env()
except Exception:
    pass


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "web_data"
RUN_DIR = DATA_DIR / "runs"
GLOBAL_DIR = DATA_DIR / "global"
BASELINE_DIR = DATA_DIR / "baselines"
BENCHMARK_DIR = DATA_DIR / "benchmarks"
MANIFEST_DIR = DATA_DIR / "manifests"

GLOBAL_KG_JSON = GLOBAL_DIR / "global_knowledge_graph.json"
PROCESSED_JSON = GLOBAL_DIR / "processed_files.json"
HISTORY_JSON = GLOBAL_DIR / "upload_history.json"

DB_DIR = PROJECT_DIR / "data"
SQLITE_PATH = DB_DIR / "learner_profiles.db"
CHROMA_PATH = DB_DIR / "chroma"

DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

DEFAULT_SIMILARITY_THRESHOLD = 0.72
DEFAULT_TOP_K = 5

KG_BACKEND = os.getenv("KG_BACKEND", "json").strip().lower()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def ensure_data_dirs() -> None:
    for path in [DATA_DIR, RUN_DIR, GLOBAL_DIR, BASELINE_DIR, BENCHMARK_DIR, MANIFEST_DIR, DB_DIR, CHROMA_PATH]:
        path.mkdir(parents=True, exist_ok=True)
