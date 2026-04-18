from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .utils import VALID_APP_TYPES, VALID_CONFIDENCE, VALID_TRI_STATE, clean_text, extract_domain


def _top_repeated_domains(rows: list[dict], top_n: int = 15) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        domain = extract_domain(row.get("developerWebsite"))
        if domain:
            counter[domain] += 1
    return counter.most_common(top_n)


def write_manual_review_candidates(rows: list[dict], destination: str) -> None:
    candidates = [row for row in rows if row.get("needs_manual_review") == "True"]
    fieldnames = sorted({key for row in candidates for key in row.keys()})
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)


def build_qc_summary(
    rows: list[dict],
    ios_count: int,
    android_count: int,
    outputs_dir: str,
    original_fieldnames: list[str] | None = None,
) -> dict:
    csv_path = Path(outputs_dir) / "ai_companion_app_evaluation.csv"
    audit_path = Path(outputs_dir) / "evaluation_audit.md"
    manual_path = Path(outputs_dir) / "manual_review_candidates.csv"
    evidence_path = Path(outputs_dir) / "evidence_log.csv"
    qc_path = Path(outputs_dir) / "qc_summary.json"

    app_types = Counter(row.get("app_type") for row in rows)
    web_counts = Counter(row.get("web_accessible") for row in rows)
    login_counts = Counter(row.get("login_required") for row in rows)
    subscription_counts = Counter(row.get("subscription_required_for_long_chat") for row in rows)
    confidence_counts = Counter(row.get("confidence") for row in rows)
    platform_counts = Counter(row.get("source_platform") for row in rows)

    summary = {
        "expected_total_rows": ios_count + android_count,
        "actual_total_rows": len(rows),
        "csv_exists": csv_path.exists(),
        "audit_exists": audit_path.exists(),
        "manual_review_exists": manual_path.exists(),
        "evidence_log_exists": evidence_path.exists(),
        "qc_summary_exists": True,
        "valid_app_type_values": all(row.get("app_type") in VALID_APP_TYPES for row in rows),
        "valid_web_accessible_values": all(row.get("web_accessible") in VALID_TRI_STATE for row in rows),
        "valid_login_required_values": all(row.get("login_required") in VALID_TRI_STATE for row in rows),
        "valid_confidence_values": all(row.get("confidence") in VALID_CONFIDENCE for row in rows),
        "row_count_matches_expected": len(rows) == ios_count + android_count,
        "all_original_fields_preserved": True,
        "missing_original_fields": [],
        "app_type_counts": dict(app_types),
        "web_accessible_counts": dict(web_counts),
        "login_required_counts": dict(login_counts),
        "subscription_required_counts": dict(subscription_counts),
        "confidence_counts": dict(confidence_counts),
        "source_platform_counts": dict(platform_counts),
        "manual_review_count": sum(1 for row in rows if row.get("needs_manual_review") == "True"),
        "low_confidence_count": sum(1 for row in rows if row.get("confidence") == "low"),
    }

    if original_fieldnames is not None:
        output_fields = set()
        for row in rows:
            output_fields.update(row.keys())
        missing_fields = sorted(set(original_fieldnames) - output_fields)
        summary["all_original_fields_preserved"] = not missing_fields
        summary["missing_original_fields"] = missing_fields

    with qc_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False, sort_keys=True)

    return summary


def write_audit_report(rows: list[dict], ios_count: int, android_count: int, destination: str, command: str) -> None:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    app_types = Counter(row.get("app_type") for row in rows)
    platforms = Counter(row.get("source_platform") for row in rows)
    web_counts = Counter(row.get("web_accessible") for row in rows)
    login_counts = Counter(row.get("login_required") for row in rows)
    subscription_counts = Counter(row.get("subscription_required_for_long_chat") for row in rows)
    manual_review_rows = [row for row in rows if row.get("needs_manual_review") == "True"]
    low_confidence_rows = [row for row in rows if row.get("confidence") == "low"]
    repeated_domains = _top_repeated_domains(rows, 15)

    lines = [
        "# Evaluation Audit",
        "",
        "## Totals",
        f"- total iOS rows: {ios_count}",
        f"- total Android rows: {android_count}",
        f"- total final rows: {len(rows)}",
        "",
        "## Counts by app_type",
    ]
    lines.extend(f"- {key}: {app_types.get(key, 0)}" for key in ["companion", "general_purpose", "mixed", "other"])
    lines.extend(
        [
            "",
            "## Counts by source_platform",
            *(f"- {key}: {value}" for key, value in sorted(platforms.items())),
            "",
            "## Counts by web_accessible",
            *(f"- {key}: {value}" for key, value in sorted(web_counts.items())),
            "",
            "## Counts by login_required",
            *(f"- {key}: {value}" for key, value in sorted(login_counts.items())),
            "",
            "## Counts by subscription_required_for_long_chat",
            *(f"- {key}: {value}" for key, value in sorted(subscription_counts.items())),
            "",
            f"## Low-confidence rows\n- {len(low_confidence_rows)}",
            "",
            f"## Manual-review rows\n- {len(manual_review_rows)}",
            "",
            "## Top 25 manual-review candidates",
        ]
    )
    for row in manual_review_rows[:25]:
        lines.append(
            f"- {clean_text(row.get('source_platform'))} | {clean_text(row.get('title'))} | "
            f"confidence={clean_text(row.get('confidence'))} | reason={clean_text(row.get('manual_review_reason'))}"
        )

    lines.extend(["", "## Top repeated developer domains"])
    for domain, count in repeated_domains:
        lines.append(f"- {domain}: {count}")

    lines.extend(
        [
            "",
            "## Known limitations",
            "- The pipeline uses metadata-first evaluation and only bounded optional web verification.",
            "- If web requests fail because of DNS, bot protection, or network restrictions, the script records low-confidence or unknown values instead of stopping.",
            "- Some login methods and subscription details are not published in app-store metadata and require manual verification.",
            "",
            "## Command used",
            f"`{command}`",
        ]
    )

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
