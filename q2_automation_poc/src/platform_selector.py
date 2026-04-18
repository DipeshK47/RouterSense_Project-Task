from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from .utils import clean_text, domain_of


@dataclass
class SelectedPlatform:
    title: str
    source_platform: str
    app_type: str
    web_accessible: str
    web_url: str
    login_required: str
    subscription_required_for_long_chat: str
    confidence: str
    app_store_url: str
    character_url: str
    reason: str


PREFERRED_HINTS = [
    "talkie",
    "hiwaifu",
    "rubii",
    "polybuzz",
    "character ai",
    "kindroid",
    "replika",
]

MANUAL_PRIORITY_BONUS = {
    "talkie": 18,
    "hiwaifu": 8,
    "rubii": 6,
    "polybuzz": 4,
}


def _score_row(row: pd.Series) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []
    app_type = clean_text(row.get("app_type"))
    title = clean_text(row.get("title"))
    web_accessible = clean_text(row.get("web_accessible"))
    login_required = clean_text(row.get("login_required"))
    long_chat = clean_text(row.get("subscription_required_for_long_chat"))
    confidence = clean_text(row.get("confidence"))
    evidence_notes = clean_text(row.get("evidence_notes")).lower()
    web_url = clean_text(row.get("web_url"))

    if app_type == "companion":
        score += 30
        reasons.append("companion app")
    elif app_type == "mixed":
        score += 20
        reasons.append("mixed app")
    else:
        score -= 50
        reasons.append("not companion or mixed")

    if web_accessible == "True":
        score += 25
        reasons.append("browser chat appears available")
    elif web_accessible == "unknown":
        score += 5
        reasons.append("web access uncertain")
    else:
        score -= 20
        reasons.append("no browser chat confirmed")

    if login_required == "False":
        score += 20
        reasons.append("guest or no-login access is favorable")
    elif login_required == "unknown":
        score += 8
        reasons.append("login complexity uncertain")
    else:
        score -= 10
        reasons.append("login required")

    if long_chat == "False":
        score += 10
        reasons.append("free tier appears sufficient for a short demo")
    elif long_chat == "unknown":
        score += 3
        reasons.append("free-tier limits uncertain")
    else:
        score -= 8
        reasons.append("subscription likely limits long chat")

    score += {"high": 10, "medium": 5, "low": 1}.get(confidence, 0)

    title_lower = title.lower()
    if any(hint in title_lower or hint in web_url.lower() for hint in PREFERRED_HINTS):
        score += 8
        reasons.append("platform has a public web footprint worth probing")

    for hint, bonus in MANUAL_PRIORITY_BONUS.items():
        if hint in title_lower or hint in web_url.lower():
            score += bonus
            reasons.append(f"manual PoC preference boost for {hint}")
            break

    if "captcha" in evidence_notes or "phone verification" in evidence_notes:
        score -= 20
        reasons.append("extra friction noted in prior evidence")

    if domain_of(web_url) in {"character.ai", "kindroid.ai", "replika.com", "replika.ai"}:
        score -= 5
        reasons.append("strong platform, but login dependency is likely")

    if "talkie" in title_lower:
        score += 10
        reasons.append("public character pages are well indexed for Talkie")

    if "hiwaifu" in title_lower or "hiwaifu" in web_url.lower():
        score -= 4
        reasons.append("auth friction for HiWaifu may require fallback")

    return score, "; ".join(reasons)


def load_q1_rows(q1_csv_path: str) -> pd.DataFrame:
    path = Path(q1_csv_path)
    if path.exists():
        return pd.read_csv(path)
    return _fallback_frame_from_raw_inputs(path.parent.parent if len(path.parents) >= 2 else Path.cwd())


def _fallback_frame_from_raw_inputs(base_dir: Path) -> pd.DataFrame:
    candidates: list[dict] = []
    possible_paths = {
        "ios": base_dir / "app_store_apps_details.json",
        "android": base_dir / "google_play_apps_details.json",
    }
    known_web_urls = {
        "talkie": "https://www.talkie-ai.com/",
        "character ai": "https://character.ai/",
        "kindroid": "https://kindroid.ai/",
        "replika": "https://replika.com/",
        "polybuzz": "https://app.polybuzz.ai/",
        "hiwaifu": "https://www.hiwaifu.com/en",
        "rubii": "https://rubii.ai/",
    }

    for source_platform, path in possible_paths.items():
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("results", []):
            title = clean_text(row.get("title"))
            title_lower = title.lower()
            app_type = "other"
            web_accessible = "unknown"
            web_url = ""
            confidence = "low"
            for hint, url in known_web_urls.items():
                if hint in title_lower:
                    app_type = "companion"
                    web_accessible = "True"
                    web_url = url
                    confidence = "medium"
                    break
            if app_type == "other":
                continue
            candidates.append(
                {
                    "title": title,
                    "source_platform": source_platform,
                    "app_type": app_type,
                    "web_accessible": web_accessible,
                    "web_url": web_url,
                    "login_required": "unknown",
                    "subscription_required_for_long_chat": "unknown",
                    "confidence": confidence,
                    "url": clean_text(row.get("url")),
                    "evidence_notes": "Fallback candidate derived from raw JSON because Q1 CSV was unavailable.",
                }
            )

    if not candidates:
        raise FileNotFoundError("Could not find Q1 CSV or usable raw JSON fallback candidates.")

    return pd.DataFrame(candidates)


def select_platform(q1_csv_path: str, output_csv_path: str) -> SelectedPlatform:
    frame = load_q1_rows(q1_csv_path)
    candidates = frame[frame["app_type"].isin(["companion", "mixed"])].copy()
    if candidates.empty:
        raise ValueError("No companion or mixed candidates found in Q1 CSV.")

    scores = candidates.apply(_score_row, axis=1)
    candidates["selection_score"] = [item[0] for item in scores]
    candidates["reason_for_choice_or_rejection"] = [item[1] for item in scores]

    chosen_idx = candidates.sort_values(
        by=["selection_score", "confidence", "title"],
        ascending=[False, False, True],
    ).index[0]

    candidates["chosen_candidate"] = False
    candidates.loc[chosen_idx, "chosen_candidate"] = True

    columns = [
        "title",
        "source_platform",
        "app_type",
        "web_accessible",
        "web_url",
        "login_required",
        "subscription_required_for_long_chat",
        "confidence",
        "chosen_candidate",
        "reason_for_choice_or_rejection",
    ]
    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)
    candidates[columns].sort_values(by=["chosen_candidate", "confidence", "title"], ascending=[False, False, True]).to_csv(
        output_csv_path,
        index=False,
    )

    chosen = candidates.loc[chosen_idx]
    title = clean_text(chosen["title"])
    web_url = clean_text(chosen["web_url"])
    character_url = web_url
    if "talkie" in title.lower():
        character_url = "https://www.talkie-ai.com/chat/community-talkie-246859608576091"
    return SelectedPlatform(
        title=title,
        source_platform=clean_text(chosen["source_platform"]),
        app_type=clean_text(chosen["app_type"]),
        web_accessible=clean_text(chosen["web_accessible"]),
        web_url=web_url,
        login_required=clean_text(chosen["login_required"]),
        subscription_required_for_long_chat=clean_text(chosen["subscription_required_for_long_chat"]),
        confidence=clean_text(chosen["confidence"]),
        app_store_url=clean_text(chosen.get("url", "")),
        character_url=character_url,
        reason=clean_text(chosen["reason_for_choice_or_rejection"]),
    )
