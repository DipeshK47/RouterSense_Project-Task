from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import time
from collections import Counter

from src.audit import build_qc_summary, write_audit_report, write_manual_review_candidates
from src.classify import classify_app
from src.evidence import make_evidence_row, write_evidence_log
from src.evaluate_fields import evaluate_metadata_fields
from src.load_data import load_all
from src.normalize import flatten_record_for_csv, normalize_records
from src.utils import clean_text, clip_note, maybe_null_web_url, normalize_url
from src.web_check import run_web_checks


EVALUATION_FIELDS = [
    "app_type",
    "web_accessible",
    "web_url",
    "login_required",
    "login_methods",
    "age_verification_required",
    "age_verification_method",
    "subscription_required_for_long_chat",
    "all_features_available_without_subscription",
    "subscription_features",
    "subscription_cost",
    "languages_supported",
    "evidence_notes",
    "evidence_urls",
    "confidence",
    "needs_manual_review",
    "manual_review_reason",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Q1 AI companion app evaluation outputs.")
    parser.add_argument("--ios", default="data/app_store_apps_details.json")
    parser.add_argument("--android", default="data/google_play_apps_details.json")
    parser.add_argument("--out", default="outputs")
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--max-web-checks", type=int, default=0)
    parser.add_argument("--web-timeout", type=int, default=10)
    return parser.parse_args()


def final_confidence(record: dict) -> str:
    if record.get("web_confidence") == "high" and record.get("classification_confidence") == "high":
        return "high"
    unknown_count = sum(
        1
        for key in [
            "web_accessible",
            "login_required",
            "age_verification_required",
            "subscription_required_for_long_chat",
            "all_features_available_without_subscription",
            "subscription_features",
            "subscription_cost",
            "languages_supported",
        ]
        if record.get(key) == "unknown"
    )
    if record.get("classification_confidence") == "low" or record.get("web_confidence") == "low":
        return "low" if unknown_count >= 3 else "medium"
    if unknown_count >= 4:
        return "low"
    return "medium"


def manual_review_reason(record: dict) -> str:
    reasons: list[str] = []
    if record.get("confidence") == "low":
        reasons.append("low confidence")
    for key in [
        "web_accessible",
        "login_required",
        "age_verification_required",
        "subscription_required_for_long_chat",
        "all_features_available_without_subscription",
    ]:
        if record.get(key) == "unknown":
            reasons.append(f"{key} unknown")
    return ", ".join(dict.fromkeys(reasons)) or "none"


def build_evidence_urls(record: dict) -> str:
    urls = [
        record.get("url"),
        record.get("developerWebsite"),
        record.get("privacyPolicy"),
    ]
    urls.extend(record.get("web_evidence_urls", []))
    seen: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized and normalized not in seen:
            seen.append(normalized)
    return "; ".join(seen)


def build_evidence_notes(record: dict) -> str:
    notes = [
        record.get("classification_note"),
        record.get("metadata_note"),
        record.get("web_note"),
    ]
    joined = " ".join(clean_text(note) for note in notes if clean_text(note))
    return clip_note(joined, limit=500)


def write_csv(rows: list[dict], destination: str) -> None:
    flattened = [flatten_record_for_csv(row) for row in rows]
    fieldnames = sorted({key for row in flattened for key in row.keys()})
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened)


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(message: str, log_path: Path | None = None) -> None:
    line = f"[{timestamp()}] {message}"
    print(line, flush=True)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def stage_summary(label: str, started_at: float, log_path: Path | None = None) -> None:
    elapsed = time.perf_counter() - started_at
    log(f"{label} completed in {elapsed:.2f}s", log_path)


def log_counter(name: str, values: list[str], log_path: Path | None = None) -> None:
    counts = Counter(values)
    rendered = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    log(f"{name}: {rendered}", log_path)


def progress_tick(current: int, total: int, label: str, log_path: Path | None = None, every: int = 100) -> None:
    if current == total or current % every == 0:
        log(f"{label}: processed {current}/{total} rows", log_path)


def main() -> None:
    overall_started_at = time.perf_counter()
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    ios_path = str((base_dir / args.ios).resolve()) if not os.path.isabs(args.ios) else args.ios
    android_path = str((base_dir / args.android).resolve()) if not os.path.isabs(args.android) else args.android
    out_dir = str((base_dir / args.out).resolve()) if not os.path.isabs(args.out) else args.out
    os.makedirs(out_dir, exist_ok=True)
    log_path = Path(out_dir) / "run_log.txt"
    if log_path.exists():
        log_path.unlink()

    log("Starting Q1 app evaluation pipeline.", log_path)
    log(f"iOS input: {ios_path}", log_path)
    log(f"Android input: {android_path}", log_path)
    log(f"Output directory: {out_dir}", log_path)
    log(
        "Runtime options: "
        + json.dumps(
            {
                "skip_web": args.skip_web,
                "max_web_checks": args.max_web_checks,
                "web_timeout": args.web_timeout,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        log_path,
    )

    started_at = time.perf_counter()
    log("Stage 1/7: loading source files", log_path)
    ios_rows, android_rows, summary = load_all(ios_path, android_path)
    stage_summary("Stage 1/7", started_at, log_path)
    log(
        f"Loaded source rows: ios={summary['ios_rows']}, android={summary['android_rows']}, total={summary['total_rows']}",
        log_path,
    )

    started_at = time.perf_counter()
    log("Stage 2/7: normalizing rows and aligning schemas", log_path)
    rows = normalize_records(ios_rows, android_rows, ios_path, android_path)
    original_fieldnames = sorted({key for row in rows for key in row.keys() if not key.startswith("source_")})
    for index, row in enumerate(rows, start=1):
        row["record_id"] = f"{row['source_platform']}::{index}"
    stage_summary("Stage 2/7", started_at, log_path)
    log(f"Normalized {len(rows)} rows into a unified table.", log_path)
    log(f"Original source fields preserved for QC: {len(original_fieldnames)}", log_path)

    evidence_rows: list[dict] = []

    started_at = time.perf_counter()
    log("Stage 3/7: classifying app types", log_path)
    total_rows = len(rows)
    for index, row in enumerate(rows, start=1):
        classification = classify_app(row)
        row.update(classification)
        evidence_rows.append(
            make_evidence_row(
                row,
                "app_type",
                row["app_type"],
                "classification_rule",
                row["classification_note"],
                clean_text(row.get("url") or row.get("developerWebsite")),
                row["classification_confidence"],
            )
        )
        progress_tick(index, total_rows, "classification", log_path)
    stage_summary("Stage 3/7", started_at, log_path)
    log_counter("app_type counts after classification", [row.get("app_type", "") for row in rows], log_path)

    started_at = time.perf_counter()
    log("Stage 4/7: deriving metadata-based evaluation fields", log_path)
    for index, row in enumerate(rows, start=1):
        metadata = evaluate_metadata_fields(row, row)
        row.update(metadata)
        for field_name in [
            "age_verification_required",
            "subscription_required_for_long_chat",
            "subscription_cost",
            "languages_supported",
        ]:
            evidence_rows.append(
                make_evidence_row(
                    row,
                    field_name,
                    row.get(field_name),
                    "metadata",
                    row.get("metadata_note", ""),
                    clean_text(row.get("url") or row.get("developerWebsite")),
                    row.get("metadata_confidence", "medium"),
                )
            )
        progress_tick(index, total_rows, "metadata evaluation", log_path)
    stage_summary("Stage 4/7", started_at, log_path)
    log_counter("login_required snapshot", [row.get("login_required", "") for row in rows], log_path)
    log_counter(
        "subscription_required_for_long_chat snapshot",
        [row.get("subscription_required_for_long_chat", "") for row in rows],
        log_path,
    )

    started_at = time.perf_counter()
    if args.skip_web:
        log("Stage 5/7: optional web checks skipped by flag", log_path)
        web_results, web_evidence = run_web_checks(rows, 0, args.web_timeout)
    else:
        log(
            f"Stage 5/7: running optional web checks with max_web_checks={args.max_web_checks} and timeout={args.web_timeout}s",
            log_path,
        )
        web_results, web_evidence = run_web_checks(rows, args.max_web_checks, args.web_timeout)
        evidence_rows.extend(web_evidence)
    stage_summary("Stage 5/7", started_at, log_path)
    if web_results:
        web_statuses = [clean_text(result.get("web_status")) or "unknown" for result in web_results.values()]
        log_counter("web check result statuses", web_statuses, log_path)
    else:
        log("No web checks produced direct result rows.", log_path)

    for row in rows:
        web_result = web_results.get(row["record_id"], {})
        if web_result:
            row.update(web_result)
            if row.get("login_required") == "unknown" and web_result.get("login_required"):
                row["login_required"] = web_result["login_required"]
            if row.get("login_methods") == "unknown" and web_result.get("login_methods"):
                row["login_methods"] = web_result["login_methods"]

        row["web_url"] = maybe_null_web_url(row.get("web_accessible", "unknown"), clean_text(row.get("web_url")))
        row["evidence_urls"] = build_evidence_urls(row)
        row["evidence_notes"] = build_evidence_notes(row)
        row["confidence"] = final_confidence(row)
        row["needs_manual_review"] = "True" if row["confidence"] == "low" else "False"
        if "unknown" in {
            row.get("web_accessible"),
            row.get("login_required"),
            row.get("age_verification_required"),
            row.get("subscription_required_for_long_chat"),
        }:
            row["needs_manual_review"] = "True"
        row["manual_review_reason"] = manual_review_reason(row)

    csv_path = os.path.join(out_dir, "ai_companion_app_evaluation.csv")
    evidence_path = os.path.join(out_dir, "evidence_log.csv")
    audit_path = os.path.join(out_dir, "evaluation_audit.md")
    manual_review_path = os.path.join(out_dir, "manual_review_candidates.csv")

    started_at = time.perf_counter()
    log("Stage 6/7: writing output artifacts", log_path)
    log(f"Writing final CSV to {csv_path}", log_path)
    write_csv(rows, csv_path)

    log(f"Writing evidence log to {evidence_path}", log_path)
    write_evidence_log(evidence_rows, evidence_path)

    log(f"Writing manual review candidates to {manual_review_path}", log_path)
    write_manual_review_candidates(rows, manual_review_path)

    log(f"Writing audit report to {audit_path}", log_path)
    command = "python run_q1_evaluation.py " + " ".join(os.sys.argv[1:])
    write_audit_report(rows, summary["ios_rows"], summary["android_rows"], audit_path, command)
    stage_summary("Stage 6/7", started_at, log_path)

    started_at = time.perf_counter()
    log("Stage 7/7: running quality control checks", log_path)
    qc_summary = build_qc_summary(
        rows,
        summary["ios_rows"],
        summary["android_rows"],
        out_dir,
        original_fieldnames=original_fieldnames,
    )
    stage_summary("Stage 7/7", started_at, log_path)

    total_elapsed = time.perf_counter() - overall_started_at
    log("Q1 pipeline complete.", log_path)
    log(f"Total rows written: {len(rows)}", log_path)
    log(f"App type counts: {qc_summary['app_type_counts']}", log_path)
    log(f"Web accessibility counts: {qc_summary['web_accessible_counts']}", log_path)
    log(f"Manual review count: {qc_summary['manual_review_count']}", log_path)
    log(f"Low-confidence rows: {qc_summary['low_confidence_count']}", log_path)
    log(f"QC summary file: {Path(out_dir) / 'qc_summary.json'}", log_path)
    log(f"Run log: {log_path}", log_path)
    log(f"End-to-end runtime: {total_elapsed:.2f}s", log_path)


if __name__ == "__main__":
    main()
