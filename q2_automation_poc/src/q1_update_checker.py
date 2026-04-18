from __future__ import annotations

from pathlib import Path

import pandas as pd

from .utils import clean_text


CHECK_FIELDS = [
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
    "confidence",
    "evidence_notes",
    "evidence_urls",
]


def generate_q1_update_report(
    q1_csv_path: str,
    selected_title: str,
    selected_source_platform: str,
    live_observations: dict,
    destination: str,
) -> None:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not Path(q1_csv_path).exists():
        output.write_text("No Q1 corrections were discovered during the Q2 PoC.\n", encoding="utf-8")
        return

    frame = pd.read_csv(q1_csv_path)
    match = frame[
        (frame["title"].astype(str) == selected_title)
        & (frame["source_platform"].astype(str) == selected_source_platform)
    ]

    if match.empty:
        output.write_text("No Q1 corrections were discovered during the Q2 PoC.\n", encoding="utf-8")
        return

    row = match.iloc[0].to_dict()
    updates: list[str] = []
    for field in CHECK_FIELDS:
        original = clean_text(row.get(field))
        observed = clean_text(live_observations.get(field))
        if observed and observed != "unknown" and original and original != observed:
            updates.append(
                "\n".join(
                    [
                        f"- field name: {field}",
                        f"  - original Q1 value: {original}",
                        f"  - corrected value: {observed}",
                        f"  - evidence from Q2: {clean_text(live_observations.get('q2_evidence_note'))}",
                        f"  - evidence URL or screenshot path: {clean_text(live_observations.get('q2_evidence_path'))}",
                        "  - reason for correction: Q2 live browser interaction contradicted the prior metadata-only evaluation.",
                    ]
                )
            )

    if not updates:
        output.write_text("No Q1 corrections were discovered during the Q2 PoC.\n", encoding="utf-8")
        return

    lines = [
        "# Q1 Updates From Q2",
        "",
        f"- app title: {selected_title}",
        f"- source platform: {selected_source_platform}",
        "",
    ]
    lines.extend(updates)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

