from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float = 30.0
    temperature: float = 0.2
    max_tokens: int = 900


class LLMClient(Protocol):
    provider: str
    model: str

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        ...
