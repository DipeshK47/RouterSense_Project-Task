from __future__ import annotations

import csv
from pathlib import Path

from .utils import clean_text, clip_note


EVIDENCE_FIELDS = [
    "source_platform",
    "title",
    "app_id",
    "field_name",
    "value",
    "evidence_type",
    "evidence_text",
    "evidence_url",
    "confidence",
]


def make_evidence_row(record: dict, field_name: str, value: object, evidence_type: str, evidence_text: str, evidence_url: str, confidence: str) -> dict:
    return {
        "source_platform": clean_text(record.get("source_platform")),
        "title": clean_text(record.get("title")),
        "app_id": clean_text(record.get("appId") or record.get("id")),
        "field_name": field_name,
        "value": clean_text(value),
        "evidence_type": evidence_type,
        "evidence_text": clip_note(evidence_text),
        "evidence_url": clean_text(evidence_url),
        "confidence": confidence,
    }


def write_evidence_log(rows: list[dict], destination: str) -> None:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

