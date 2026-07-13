from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from gridweather.llm.base import LLMConfig, LLMMessage, LLMResponse


class OpenAICompatibleChatClient:
    """Minimal stdlib client for OpenAI-compatible chat-completions APIs.

    DeepSeek, Zhipu GLM, Qwen/DashScope compatible mode, and OpenAI can all be
    called through this adapter. The project keeps this dependency-light so the
    original offline demo still runs without installing provider SDKs.
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.provider = config.provider
        self.model = config.model

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [message.__dict__ for message in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.provider} API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.provider} API request failed: {exc.reason}") from exc

        content = _extract_chat_content(raw)
        return LLMResponse(
            content=content,
            provider=self.provider,
            model=str(payload["model"]),
            raw=raw,
        )


def _extract_chat_content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if not choices:
        raise RuntimeError(f"LLM response has no choices: {raw}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content or "").strip()
