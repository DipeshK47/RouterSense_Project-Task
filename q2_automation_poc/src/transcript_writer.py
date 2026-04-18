from __future__ import annotations

from .utils import write_csv, write_json


def write_transcripts(transcript_rows: list[dict], csv_path: str, json_path: str) -> None:
    write_csv(transcript_rows, csv_path)
    write_json(transcript_rows, json_path)

