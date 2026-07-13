from __future__ import annotations

import os

from gridweather.llm.base import LLMConfig, LLMClient
from gridweather.llm.openai_compatible import OpenAICompatibleChatClient


PROVIDER_DEFAULTS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "zhipu": {
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
    },
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
}


def build_llm_client(provider: str | None = None) -> LLMClient | None:
    """Build an optional LLM client from environment variables.

    The default route is domestic-first: DeepSeek for text/planning, with Zhipu
    or Qwen selectable through GRIDWEATHER_LLM_PROVIDER. Returning None is an
    intentional offline fallback for the repository's reproducible demo mode.
    """

    if os.getenv("GRIDWEATHER_LLM_ENABLED", "0").lower() not in {"1", "true", "yes", "on"}:
        return None

    selected = (provider or os.getenv("GRIDWEATHER_LLM_PROVIDER") or "deepseek").lower()
    if selected not in PROVIDER_DEFAULTS:
        allowed = ", ".join(sorted(PROVIDER_DEFAULTS))
        raise ValueError(f"Unsupported LLM provider '{selected}'. Expected one of: {allowed}")

    defaults = PROVIDER_DEFAULTS[selected]
    api_key_env = os.getenv("GRIDWEATHER_LLM_API_KEY_ENV", defaults["api_key_env"])
    api_key = os.getenv(api_key_env, "").strip()
    if not api_key:
        return None

    model = os.getenv("GRIDWEATHER_LLM_MODEL", defaults["model"])
    base_url = os.getenv("GRIDWEATHER_LLM_BASE_URL", defaults["base_url"])
    timeout = float(os.getenv("GRIDWEATHER_LLM_TIMEOUT_SECONDS", "30"))
    temperature = float(os.getenv("GRIDWEATHER_LLM_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("GRIDWEATHER_LLM_MAX_TOKENS", "900"))

    config = LLMConfig(
        provider=selected,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return OpenAICompatibleChatClient(config)
