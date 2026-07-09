from __future__ import annotations

from dataclasses import dataclass, field

from gridweather.retrieval.chunking import tokenize


@dataclass
class Message:
    role: str
    content: str


@dataclass
class MemoryState:
    summary: str = ""
    recent: list[Message] = field(default_factory=list)


def estimate_tokens(text: str) -> int:
    return max(1, int(len(tokenize(text)) * 1.3))


class BudgetedConversationMemory:
    """Keep a compact summary plus recent turns under a token budget."""

    def __init__(self, max_tokens: int = 1200, recent_turns: int = 6) -> None:
        self.max_tokens = max_tokens
        self.recent_turns = recent_turns
        self.state = MemoryState()

    def add(self, role: str, content: str) -> None:
        self.state.recent.append(Message(role, content))
        if len(self.state.recent) > self.recent_turns:
            overflow = self.state.recent[:-self.recent_turns]
            self.state.recent = self.state.recent[-self.recent_turns :]
            self._summarize_overflow(overflow)
        self._enforce_budget()

    def _summarize_overflow(self, messages: list[Message]) -> None:
        facts = []
        for msg in messages:
            compact = " ".join(msg.content.split())
            facts.append(f"{msg.role}: {compact[:180]}")
        merged = (self.state.summary + "\n" + "\n".join(facts)).strip()
        self.state.summary = merged[-2500:]

    def _enforce_budget(self) -> None:
        while self.total_tokens() > self.max_tokens and self.state.recent:
            self._summarize_overflow([self.state.recent.pop(0)])
        if self.total_tokens() > self.max_tokens:
            self.state.summary = self.state.summary[-max(200, int(self.max_tokens * 3)) :]

    def total_tokens(self) -> int:
        text = self.state.summary + "\n" + "\n".join(m.content for m in self.state.recent)
        return estimate_tokens(text)

    def prompt_context(self) -> str:
        parts = []
        if self.state.summary:
            parts.append("Summary memory:\n" + self.state.summary)
        if self.state.recent:
            parts.append("Recent turns:\n" + "\n".join(f"{m.role}: {m.content}" for m in self.state.recent))
        return "\n\n".join(parts)

