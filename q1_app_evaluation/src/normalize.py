from __future__ import annotations

from pathlib import Path

from .utils import serialize_for_csv


def attach_source_fields(rows: list[dict], source_platform: str, source_file: str) -> list[dict]:
    normalized: list[dict] = []
    file_name = Path(source_file).name
    for index, row in enumerate(rows, start=1):
        enriched = dict(row)
        enriched["source_platform"] = source_platform
        enriched["source_file"] = file_name
        enriched["source_row_number"] = index
        normalized.append(enriched)
    return normalized


def normalize_records(ios_rows: list[dict], android_rows: list[dict], ios_path: str, android_path: str) -> list[dict]:
    combined = []
    combined.extend(attach_source_fields(ios_rows, "ios", ios_path))
    combined.extend(attach_source_fields(android_rows, "android", android_path))
    return combined


def flatten_record_for_csv(record: dict) -> dict:
    return {key: serialize_for_csv(value) for key, value in record.items()}

