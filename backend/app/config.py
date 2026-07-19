import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
    RAG_CANDIDATE_K = int(os.getenv("RAG_CANDIDATE_K", "12"))
    RAG_USE_HYBRID = os.getenv("RAG_USE_HYBRID", "true").lower() in ("1", "true", "yes")
    RAG_USE_RERANK = os.getenv("RAG_USE_RERANK", "true").lower() in ("1", "true", "yes")
    RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
    # After hybrid+rerank: if top score < threshold, rewrite query and retrieve once more.
    RAG_CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "0.35"))
    RAG_CONFIDENCE_REWRITE = os.getenv("RAG_CONFIDENCE_REWRITE", "true").lower() in ("1", "true", "yes")

    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#incidents")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "INC")

    # LangSmith
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "incident-suite-evals")

    # Webhook
    WEBHOOK_API_KEYS = os.getenv("WEBHOOK_API_KEYS", "")

    # HF
    HF_TOKEN = os.getenv("HF_TOKEN", "")


config = Config()
assert config.OPENROUTER_API_KEY, "OPENROUTER_API_KEY must be set in .env"

if config.LANGSMITH_API_KEY:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", config.LANGSMITH_PROJECT)
    os.environ.setdefault("LANGSMITH_API_KEY", config.LANGSMITH_API_KEY)
