from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .utils import clean_text, clip_note, extract_domain, normalize_key, normalize_url


KNOWN_WEB_OVERRIDES = {
    "chatgpt": {
        "web_accessible": "True",
        "web_url": "https://chatgpt.com/",
        "login_required": "True",
        "login_methods": "unknown",
        "note": "Official web app exists at chatgpt.com.",
        "evidence_urls": ["https://chatgpt.com/"],
    },
    "google gemini": {
        "web_accessible": "True",
        "web_url": "https://gemini.google.com/",
        "login_required": "True",
        "login_methods": "Google",
        "note": "Official web app exists at gemini.google.com.",
        "evidence_urls": ["https://gemini.google.com/"],
    },
    "claude by anthropic": {
        "web_accessible": "True",
        "web_url": "https://claude.ai/",
        "login_required": "True",
        "login_methods": "email/password, Google",
        "note": "Official web app exists at claude.ai.",
        "evidence_urls": ["https://claude.ai/"],
    },
    "microsoft copilot": {
        "web_accessible": "True",
        "web_url": "https://copilot.microsoft.com/",
        "login_required": "True",
        "login_methods": "Microsoft",
        "note": "Official web app exists at copilot.microsoft.com.",
        "evidence_urls": ["https://copilot.microsoft.com/"],
    },
    "grok ai chat video": {
        "web_accessible": "True",
        "web_url": "https://grok.com/",
        "login_required": "unknown",
        "login_methods": "unknown",
        "note": "Official web entry point exists at grok.com.",
        "evidence_urls": ["https://grok.com/"],
    },
    "deepseek ai assistant": {
        "web_accessible": "True",
        "web_url": "https://chat.deepseek.com/",
        "login_required": "unknown",
        "login_methods": "unknown",
        "note": "Official consumer chat is available on the DeepSeek website.",
        "evidence_urls": ["https://www.deepseek.com/", "https://chat.deepseek.com/"],
    },
    "perplexity ask anything": {
        "web_accessible": "True",
        "web_url": "https://www.perplexity.ai/",
        "login_required": "unknown",
        "login_methods": "unknown",
        "note": "Official web search/chat interface exists at perplexity.ai.",
        "evidence_urls": ["https://www.perplexity.ai/"],
    },
    "poe fast ai chat": {
        "web_accessible": "True",
        "web_url": "https://poe.com/",
        "login_required": "True",
        "login_methods": "unknown",
        "note": "Official web interface exists at poe.com.",
        "evidence_urls": ["https://poe.com/"],
    },
    "pi your personal ai": {
        "web_accessible": "True",
        "web_url": "https://pi.ai/",
        "login_required": "True",
        "login_methods": "phone",
        "note": "Official web interface exists at pi.ai.",
        "evidence_urls": ["https://pi.ai/"],
    },
    "character ai chat talk text": {
        "web_accessible": "True",
        "web_url": "https://character.ai/",
        "login_required": "True",
        "login_methods": "Google, Apple, email/password",
        "note": "Official character chat website exists at character.ai.",
        "evidence_urls": ["https://character.ai/"],
    },
    "replika ai friend": {
        "web_accessible": "True",
        "web_url": "https://replika.com/",
        "login_required": "True",
        "login_methods": "unknown",
        "note": "Official website and help center state browser access is supported.",
        "evidence_urls": ["https://replika.com/", "https://help.replika.com/hc/en-us/articles/115001094491-What-platforms-devices-are-supported-"],
    },
    "replika my ai friend": {
        "web_accessible": "True",
        "web_url": "https://replika.com/",
        "login_required": "True",
        "login_methods": "unknown",
        "note": "Official website and help center state browser access is supported.",
        "evidence_urls": ["https://replika.com/", "https://help.replika.com/hc/en-us/articles/115001094491-What-platforms-devices-are-supported-"],
    },
    "kindroid your personal ai": {
        "web_accessible": "True",
        "web_url": "https://kindroid.ai/",
        "login_required": "True",
        "login_methods": "email/password, Google, Apple",
        "note": "Official website provides browser access.",
        "evidence_urls": ["https://kindroid.ai/"],
    },
    "polybuzz chat with characters": {
        "web_accessible": "True",
        "web_url": "https://app.polybuzz.ai/",
        "login_required": "unknown",
        "login_methods": "unknown",
        "note": "Developer website points to the browser-based PolyBuzz experience.",
        "evidence_urls": ["https://app.polybuzz.ai/"],
    },
    "polybuzz chat with ai friends": {
        "web_accessible": "True",
        "web_url": "https://app.polybuzz.ai/",
        "login_required": "unknown",
        "login_methods": "unknown",
        "note": "Developer website points to the browser-based PolyBuzz experience.",
        "evidence_urls": ["https://app.polybuzz.ai/"],
    },
    "talkie creative ai community": {
        "web_accessible": "True",
        "web_url": "https://www.talkie-ai.com/",
        "login_required": "unknown",
        "login_methods": "unknown",
        "note": "Official Talkie website offers browser chat entry points.",
        "evidence_urls": ["https://www.talkie-ai.com/"],
    },
}

BLOCKED_STATUSES = {401, 403, 429}


@dataclass
class WebCheckResult:
    status: str
    final_url: str
    page_title: str
    note: str
    evidence_urls: list[str]
    web_accessible: str = "unknown"
    web_url: str = "null"
    login_required: str = "unknown"
    login_methods: str = "unknown"


def _classify_page(url: str, response: requests.Response) -> WebCheckResult:
    final_url = normalize_url(response.url or url)
    if response.status_code in BLOCKED_STATUSES:
        return WebCheckResult(
            status="blocked",
            final_url=final_url,
            page_title="",
            note=f"Web fetch returned status {response.status_code}.",
            evidence_urls=[final_url],
        )
    soup = BeautifulSoup(response.text, "html.parser")
    title = clean_text(soup.title.string if soup.title and soup.title.string else "")
    text = clean_text(" ".join(soup.stripped_strings))
    lower = text.lower()
    login_page = any(token in lower for token in ["sign in", "login", "continue with google", "continue with apple"])
    chat_signal = any(token in lower for token in ["chat", "character", "assistant", "companion", "start chatting", "messages"])
    marketing_signal = any(token in lower for token in ["download on the app store", "google play", "get the app", "privacy policy", "terms of service"])
    pricing_signal = any(token in lower for token in ["pricing", "subscription", "plans", "premium"])

    status = "unknown"
    web_accessible = "unknown"
    web_url = "null"
    login_required = "unknown"
    login_methods = "unknown"
    note = "Fetched official website."

    if login_page and chat_signal:
        status = "login_page"
        web_accessible = "True"
        web_url = final_url
        login_required = "True"
        note = "Fetched page looks like a browser-based login or entry point for chat."
    elif chat_signal and not marketing_signal:
        status = "web_chat_possible"
        web_accessible = "True"
        web_url = final_url
        note = "Fetched page contains chat or assistant signals beyond pure marketing copy."
    elif pricing_signal and not chat_signal:
        status = "pricing_page"
        note = "Fetched page looks like pricing or plan information."
    elif marketing_signal:
        status = "marketing_only"
        web_accessible = "False"
        note = "Fetched page looks like marketing or app-download content only."

    return WebCheckResult(
        status=status,
        final_url=final_url,
        page_title=title,
        note=note,
        evidence_urls=[final_url],
        web_accessible=web_accessible,
        web_url=web_url,
        login_required=login_required,
        login_methods=login_methods,
    )


def _fetch_url(url: str, timeout: int) -> WebCheckResult:
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Q1 App Evaluation Bot)"},
        )
        return _classify_page(url, response)
    except requests.RequestException as exc:
        error = clean_text(str(exc))
        status = "unavailable"
        if "name or service not known" in error.lower() or "failed to resolve" in error.lower():
            status = "unavailable"
        return WebCheckResult(
            status=status,
            final_url=normalize_url(url),
            page_title="",
            note=f"Web fetch failed: {error}",
            evidence_urls=[normalize_url(url)],
        )


def candidate_records(records: Iterable[dict]) -> list[dict]:
    candidates = []
    for record in records:
        title_key = normalize_key(record.get("title"))
        if title_key in KNOWN_WEB_OVERRIDES or clean_text(record.get("developerWebsite")):
            candidates.append(record)
    return candidates


def run_web_checks(records: list[dict], max_checks: int, timeout: int) -> tuple[dict[str, dict], list[dict]]:
    web_results: dict[str, dict] = {}
    evidence_rows: list[dict] = []
    checked_fetches = 0

    for record in candidate_records(records):
        record_id = record["record_id"]
        title_key = normalize_key(record.get("title"))
        override = KNOWN_WEB_OVERRIDES.get(title_key)
        if override:
            web_results[record_id] = {
                "web_accessible": override["web_accessible"],
                "web_url": override["web_url"],
                "login_required": override["login_required"],
                "login_methods": override["login_methods"],
                "web_note": override["note"],
                "web_confidence": "high",
                "web_status": "override",
                "web_checked_url": override["web_url"],
                "web_evidence_urls": override["evidence_urls"],
            }
            continue

        if max_checks <= 0 or checked_fetches >= max_checks:
            continue

        url = clean_text(record.get("developerWebsite"))
        if not url:
            continue
        result = _fetch_url(url, timeout)
        checked_fetches += 1
        web_results[record_id] = {
            "web_accessible": result.web_accessible,
            "web_url": result.web_url,
            "login_required": result.login_required,
            "login_methods": result.login_methods,
            "web_note": result.note,
            "web_confidence": "high" if result.status in {"login_page", "web_chat_possible", "marketing_only"} else "low",
            "web_status": result.status,
            "web_checked_url": result.final_url,
            "web_evidence_urls": result.evidence_urls,
        }
        evidence_rows.append(
            {
                "source_platform": record.get("source_platform"),
                "title": clean_text(record.get("title")),
                "app_id": clean_text(record.get("appId") or record.get("id")),
                "field_name": "web_fetch",
                "value": result.status,
                "evidence_type": "web_fetch",
                "evidence_text": clip_note(f"{result.note} Title: {result.page_title}"),
                "evidence_url": result.final_url,
                "confidence": web_results[record_id]["web_confidence"],
            }
        )

    return web_results, evidence_rows
