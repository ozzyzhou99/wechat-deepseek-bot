"""Small text utilities independent of WeChat."""

from __future__ import annotations

from typing import List


def chunk_text(text: str, max_chars: int = 2000) -> List[str]:
    """Split long text at paragraph/newline boundaries where possible."""

    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, max_chars + 1)
        if cut < max_chars // 3:
            cut = remaining.rfind(" ", 0, max_chars + 1)
        if cut < max_chars // 3:
            cut = max_chars
        chunk = remaining[:cut].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].lstrip(" \n\r")
    return chunks
