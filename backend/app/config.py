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

    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#incidents")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "INC")


config = Config()
assert config.OPENROUTER_API_KEY, "OPENROUTER_API_KEY must be set in .env"