from langchain_openai import ChatOpenAI
from app.config import config


def get_llm(temperature: float | None = None, api_key: str | None = None) -> ChatOpenAI:
    """Chat model via OpenRouter (OpenAI-compatible). Model = openai/gpt-4o-mini.

    api_key: per-request override supplied by the user via the frontend.
             Falls back to the OPENROUTER_API_KEY env var if not provided.

    To use real OpenAI:  remove base_url, set api_key to an OpenAI key.
    To use Anthropic:    pip install langchain-anthropic and return ChatAnthropic(...).
    Only this function changes when swapping providers.
    """
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=api_key or config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        temperature=config.LLM_TEMPERATURE if temperature is None else temperature,
    )