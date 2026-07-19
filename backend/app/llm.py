from __future__ import annotations

import time
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agent_logging import log_llm_exchange, timed_ms
from app.config import config


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """Chat model via OpenRouter (OpenAI-compatible). Model = openai/gpt-4o-mini.

    To use real OpenAI:  remove base_url, set api_key to an OpenAI key.
    To use Anthropic:    pip install langchain-anthropic and return ChatAnthropic(...).
    Only this function changes when swapping providers.
    """
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        temperature=config.LLM_TEMPERATURE if temperature is None else temperature,
    )


def invoke_llm(
    agent: str,
    llm: Any,
    prompt: str | list,
    *,
    model: str | None = None,
) -> Any:
    """Invoke an LLM chain and log request/response as structured JSON.

    Use this for every agent LLM call so prompts and structured outputs are
    visible in the server logs.
    """
    model_name = model or config.LLM_MODEL
    started = time.perf_counter()
    try:
        result = llm.invoke(prompt)
    except Exception as exc:
        log_llm_exchange(
            agent,
            request=prompt,
            error=f"{type(exc).__name__}: {exc}",
            latency_ms=timed_ms(started),
            model=model_name,
        )
        raise

    response: Any = result
    if isinstance(result, BaseModel):
        response = result.model_dump()

    log_llm_exchange(
        agent,
        request=prompt,
        response=response,
        latency_ms=timed_ms(started),
        model=model_name,
    )
    return result
