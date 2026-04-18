from __future__ import annotations

from pathlib import Path


def load_messages(path: str, max_messages: int | None = None) -> list[str]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Message file not found: {source}")
    messages = [line.strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if max_messages is not None:
        messages = messages[:max_messages]
    if len(messages) < 10:
        raise ValueError("input_messages.txt must contain at least 10 non-empty messages.")
    return messages

