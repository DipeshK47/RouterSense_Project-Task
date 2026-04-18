from __future__ import annotations

import json
import math
import re
from typing import Iterable
from urllib.parse import urlparse


VALID_APP_TYPES = {"companion", "general_purpose", "mixed", "other"}
VALID_TRI_STATE = {"True", "False", "unknown"}
VALID_CONFIDENCE = {"high", "medium", "low"}

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTISPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    text = ZERO_WIDTH_RE.sub("", str(value))
    return MULTISPACE_RE.sub(" ", text).strip()


def normalize_key(value: object) -> str:
    text = clean_text(value).lower()
    text = NON_ALNUM_RE.sub(" ", text)
    return MULTISPACE_RE.sub(" ", text).strip()


def normalize_url(url: object) -> str:
    text = clean_text(url)
    if not text:
        return ""
    return text.rstrip("/")


def extract_domain(url: object) -> str:
    parsed = urlparse(normalize_url(url))
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def serialize_for_csv(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def dedupe_preserve_order(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        if text not in seen:
            seen.add(text)
            output.append(text)
    return output


def join_unique(values: Iterable[object], separator: str = ", ") -> str:
    unique = dedupe_preserve_order(values)
    return separator.join(unique) if unique else ""


def title_or_app_id(record: dict) -> str:
    return clean_text(record.get("title") or record.get("trackName") or record.get("appId") or record.get("id"))


def boolish(value: bool | None, unknown: bool = False) -> str:
    if value is True:
        return "True"
    if value is False:
        return "False"
    return "unknown" if unknown else ""


def content_blob(record: dict) -> str:
    parts = [
        record.get("title"),
        record.get("summary"),
        record.get("description"),
        record.get("primaryGenre"),
        record.get("genre"),
        record.get("genres"),
        record.get("categories"),
        record.get("contentRating"),
        record.get("developerWebsite"),
        record.get("url"),
    ]
    return clean_text(" ".join(clean_text(part) for part in parts if part not in (None, "")))


def monthly_estimate(amount: float, period: str) -> float:
    period = period.lower()
    if period in {"month", "monthly"}:
        return amount
    if period in {"week", "weekly"}:
        return amount * 4
    if period in {"year", "yearly", "annual", "annually"}:
        return amount / 12
    return amount


def format_currency(currency: str | None) -> str:
    text = clean_text(currency).upper()
    return text if text else "USD"


PRICE_PATTERNS = [
    re.compile(
        r"(?P<currency>USD|\$|EUR|€|GBP|£|JPY|¥|CAD|AUD)?\s*"
        r"(?P<amount>\d+(?:\.\d{1,2})?)\s*/\s*(?P<period>week|month|year)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<currency>USD|\$|EUR|€|GBP|£|JPY|¥|CAD|AUD)?\s*"
        r"(?P<amount>\d+(?:\.\d{1,2})?)\s+per\s+(?P<period>week|month|year)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<period>weekly|monthly|yearly|annual)\s*(?:plan|subscription)?"
        r"[^0-9]{0,20}(?P<currency>USD|\$|EUR|€|GBP|£|JPY|¥|CAD|AUD)?\s*"
        r"(?P<amount>\d+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    ),
]


def extract_price_from_text(text: str, currency_hint: str = "USD") -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return "unknown"
    for pattern in PRICE_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        amount = float(match.group("amount"))
        raw_currency = match.groupdict().get("currency") or currency_hint
        currency = format_currency(raw_currency)
        period = match.group("period")
        if raw_currency == "$":
            currency = "USD"
        elif raw_currency == "€":
            currency = "EUR"
        elif raw_currency == "£":
            currency = "GBP"
        elif raw_currency == "¥":
            currency = "JPY"
        monthly = monthly_estimate(amount, period)
        if period.lower() in {"month", "monthly"}:
            return f"{currency} {amount:.2f}/month"
        return (
            f"{currency} {amount:.2f}/{period.lower()}, "
            f"approximately {currency} {monthly:.2f}/month"
        )
    return "unknown"


def iap_range_to_text(iap_range: object, currency_hint: str = "USD") -> str:
    text = clean_text(iap_range)
    if not text:
        return "unknown"
    return f"IAP range {format_currency(currency_hint)} {text}, exact monthly plan unknown"


def parse_json_like(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    text = clean_text(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def detect_languages(value: object) -> str:
    if not value:
        return "unknown"
    parsed = parse_json_like(value)
    if isinstance(parsed, list):
        langs = [clean_text(item).upper() for item in parsed if clean_text(item)]
        return "|".join(dedupe_preserve_order(langs)) if langs else "unknown"
    text = clean_text(parsed).upper()
    return text if text else "unknown"


def clip_note(note: str, limit: int = 300) -> str:
    note = clean_text(note)
    if len(note) <= limit:
        return note
    return note[: limit - 3].rstrip() + "..."


def confidence_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 0)


def min_confidence(left: str, right: str) -> str:
    return left if confidence_rank(left) <= confidence_rank(right) else right


def max_confidence(left: str, right: str) -> str:
    return left if confidence_rank(left) >= confidence_rank(right) else right


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_unknown(value: object) -> bool:
    return clean_text(value).lower() in {"", "unknown", "null", "none available"}


def maybe_null_web_url(web_accessible: str, web_url: str) -> str:
    if web_accessible != "True":
        return "null"
    return web_url or "null"

