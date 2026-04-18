from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def safe_slug(text: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in clean_text(text))
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "item"


def append_log(log_path: str | Path, message: str) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{now_iso()}] {message}"
    print(line, flush=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(data: object, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def domain_of(url: str) -> str:
    parsed = urlparse(clean_text(url))
    domain = parsed.netloc.lower()
    return domain[4:] if domain.startswith("www.") else domain


def first_non_empty(values: Iterable[object], default: str = "") -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return default
