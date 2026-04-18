from __future__ import annotations

import json
from pathlib import Path


def load_source(path: str) -> list[dict]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or "results" not in payload:
        raise ValueError(f"Unexpected JSON structure in {source}; expected top-level 'results' key.")
    rows = payload["results"]
    if not isinstance(rows, list):
        raise ValueError(f"Unexpected 'results' structure in {source}; expected list.")
    return rows


def load_all(ios_path: str, android_path: str) -> tuple[list[dict], list[dict], dict]:
    ios_rows = load_source(ios_path)
    android_rows = load_source(android_path)
    summary = {
        "ios_rows": len(ios_rows),
        "android_rows": len(android_rows),
        "total_rows": len(ios_rows) + len(android_rows),
    }
    return ios_rows, android_rows, summary

