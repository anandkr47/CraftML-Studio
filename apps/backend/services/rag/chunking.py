"""Recursive text chunking with overlap."""

import re
from typing import List

SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split(text: str, size: int, level: int) -> List[str]:
    """Split ``text`` into pieces no longer than ``size``, preferring coarse separators."""
    if len(text) <= size:
        return [text]
    if level >= len(SEPARATORS):
        return [text[i : i + size] for i in range(0, len(text), size)]

    sep = SEPARATORS[level]
    pieces: List[str] = []
    current = ""
    for part in text.split(sep):
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if len(part) > size:
            pieces.extend(_split(part, size, level + 1))
            current = ""
        else:
            current = part
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    """Chunks of about ``chunk_size`` characters; each starts with the tail of the previous one."""
    text = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    if not text:
        return []

    pieces = [p.strip() for p in _split(text, chunk_size - overlap, 0) if p.strip()]
    chunks = []
    for i, piece in enumerate(pieces):
        if i and overlap:
            tail = pieces[i - 1][-overlap:]
            piece = f"{tail} {piece}"
        chunks.append(piece)
    return chunks
