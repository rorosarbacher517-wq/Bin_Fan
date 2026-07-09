from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    start: int
    end: int
    strategy: str


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def fixed_window_chunks(text: str, size: int = 180, overlap: int = 40) -> list[Chunk]:
    tokens = tokenize(text)
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    chunks: list[Chunk] = []
    step = size - overlap
    for start in range(0, len(tokens), step):
        end = min(start + size, len(tokens))
        window = " ".join(tokens[start:end])
        chunks.append(Chunk(f"fixed-{len(chunks)}", window, start, end, "fixed_window"))
        if end == len(tokens):
            break
    return chunks


def paragraph_chunks(text: str, max_tokens: int = 220) -> list[Chunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    token_cursor = 0
    buf: list[str] = []
    buf_start = 0
    for para in paragraphs:
        toks = tokenize(para)
        if not buf:
            buf_start = token_cursor
        if buf and len(tokenize("\n\n".join(buf))) + len(toks) > max_tokens:
            joined = "\n\n".join(buf)
            end = buf_start + len(tokenize(joined))
            chunks.append(Chunk(f"para-{len(chunks)}", joined, buf_start, end, "paragraph"))
            buf = [para]
            buf_start = token_cursor
        else:
            buf.append(para)
        token_cursor += len(toks)
    if buf:
        joined = "\n\n".join(buf)
        end = buf_start + len(tokenize(joined))
        chunks.append(Chunk(f"para-{len(chunks)}", joined, buf_start, end, "paragraph"))
    return chunks

