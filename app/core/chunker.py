"""Structure-first chunker: split a note by heading tree, merge/split to size."""
from __future__ import annotations

import re

MIN_TOKENS = 200
MAX_TOKENS = 800


def estimate_tokens(text: str) -> int:
    # rough estimate: Chinese chars ~= 1 token per 2 chars incl. markup
    return max(1, len(text) // 2)


def _sections(content: str) -> list[dict]:
    """Split markdown into sections, each tagged with its heading path."""
    sections = []
    stack: list[str] = []
    buf: list[str] = []
    for line in content.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if buf:
                sections.append({"path": " > ".join(stack), "text": "\n".join(buf).strip()})
                buf = []
            level = len(m.group(1))
            stack = stack[: level - 1] + [m.group(2).strip()]
        buf.append(line)
    if buf:
        sections.append({"path": " > ".join(stack), "text": "\n".join(buf).strip()})
    return [s for s in sections if s["text"]]


def chunk_note(note_id: str, content: str) -> list[dict]:
    """Greedy merge small sections upward; split oversized at blank lines."""
    sections = _sections(content)
    merged: list[dict] = []
    cur = None
    for sec in sections:
        if cur and estimate_tokens(cur["text"] + "\n\n" + sec["text"]) <= MAX_TOKENS:
            cur["text"] += "\n\n" + sec["text"]
            if sec["path"]:
                cur["path"] = sec["path"]
        else:
            if cur:
                merged.append(cur)
            cur = dict(sec)
    if cur:
        merged.append(cur)

    chunks: list[dict] = []
    for block in merged:
        text, path = block["text"], block["path"]
        if estimate_tokens(text) <= MAX_TOKENS * 1.5:
            chunks.append({"path": path, "text": text})
            continue
        # split oversized block at paragraph boundaries
        part, parts = "", []
        for para in re.split(r"\n\s*\n", text):
            if part and estimate_tokens(part + "\n\n" + para) > MAX_TOKENS:
                parts.append(part)
                part = para
            else:
                part = (part + "\n\n" + para) if part else para
        if part:
            parts.append(part)
        chunks.extend({"path": path, "text": p} for p in parts)

    return [
        {
            "chunk_id": f"{note_id}-c{i:02d}",
            "note_id": note_id,
            "heading_path": c["path"],
            "content": c["text"],
            "tokens": estimate_tokens(c["text"]),
            "ord": i,
        }
        for i, c in enumerate(chunks)
    ]
