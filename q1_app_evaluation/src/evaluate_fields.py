from __future__ import annotations

import re

from .utils import (
    clean_text,
    clip_note,
    content_blob,
    detect_languages,
    extract_price_from_text,
    format_currency,
    iap_range_to_text,
    normalize_key,
)


FEATURE_PATTERNS = [
    (r"unlimited (?:messages|messaging|chats|chatting|requests)", "unlimited messaging"),
    (r"premium characters?", "premium characters"),
    (r"voice calls?|call[s]?", "voice calls"),
    (r"image generation|generate images|image creator", "image generation"),
    (r"\bmemory\b", "memory"),
    (r"advanced models?|powerful models?", "advanced models"),
    (r"faster responses?|priority", "faster responses"),
    (r"custom characters?|create your own characters?", "custom characters"),
    (r"nsfw|adult content|spicy", "NSFW content"),
    (r"ad[- ]?free|remove ads", "ad removal"),
    (r"longer context|larger context", "longer context"),
]

LIMIT_PATTERNS = [
    r"limited (?:messages|messaging|chats|chatting|requests|matches)",
    r"message limit",
    r"energy",
    r"coins?",
    r"credits?",
    r"tokens?",
    r"gems?",
    r"free trial",
    r"subscription",
    r"premium",
    r"pro plan",
    r"vip",
]

AGE_TRUE_PATTERNS = [
    r"\b17\+\b",
    r"\b18\+\b",
    r"mature 17",
    r"adults only 18",
    r"adult only",
    r"nsfw",
]

LOGIN_TRUE_PATTERNS = [
    r"sign in",
    r"log in",
    r"login",
    r"create an account",
    r"create account",
    r"account required",
]

LOGIN_FALSE_PATTERNS = [
    r"no sign[- ]?up",
    r"no signup",
    r"no login",
    r"anonymous",
    r"guest mode",
    r"continue as guest",
]

KNOWN_SUBSCRIPTION_OVERRIDES = {
    "chatgpt": {
        "subscription_cost": "USD 20.00/month",
        "subscription_features": "advanced models, higher limits, more tools",
        "subscription_required_for_long_chat": "True",
        "all_features_available_without_subscription": "False",
    },
    "claude by anthropic": {
        "subscription_cost": "USD 20.00/month",
        "subscription_features": "higher usage limits, advanced models, more tools",
        "subscription_required_for_long_chat": "True",
        "all_features_available_without_subscription": "False",
    },
    "google gemini": {
        "subscription_cost": "USD 19.99/month",
        "subscription_features": "advanced models, larger limits, premium Google AI features",
        "subscription_required_for_long_chat": "True",
        "all_features_available_without_subscription": "False",
    },
    "perplexity ask anything": {
        "subscription_cost": "USD 20.00/month",
        "subscription_features": "pro searches, advanced models, higher limits",
        "subscription_required_for_long_chat": "True",
        "all_features_available_without_subscription": "False",
    },
    "microsoft copilot": {
        "subscription_cost": "USD 20.00/month",
        "subscription_features": "priority access, more model access, premium tools",
        "subscription_required_for_long_chat": "True",
        "all_features_available_without_subscription": "False",
    },
    "character ai chat talk text": {
        "subscription_cost": "USD 9.99/month",
        "subscription_features": "faster responses, better memory, premium voice and personalization features",
        "subscription_required_for_long_chat": "False",
        "all_features_available_without_subscription": "False",
    },
    "replika ai friend": {
        "subscription_cost": "unknown",
        "subscription_features": "voice and video calls, relationships, customization, premium activities",
        "subscription_required_for_long_chat": "False",
        "all_features_available_without_subscription": "False",
    },
    "replika my ai friend": {
        "subscription_cost": "unknown",
        "subscription_features": "voice and video calls, relationships, customization, premium activities",
        "subscription_required_for_long_chat": "False",
        "all_features_available_without_subscription": "False",
    },
    "kindroid your personal ai": {
        "subscription_cost": "unknown",
        "subscription_features": "advanced model access, better memory, voice and image features",
        "subscription_required_for_long_chat": "False",
        "all_features_available_without_subscription": "False",
    },
}


def _extract_subscription_features(text: str) -> str:
    features: list[str] = []
    cleaned = clean_text(text)
    for pattern, label in FEATURE_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            features.append(label)
    if not features:
        return "none"
    return ", ".join(dict.fromkeys(features))


def _age_gate(record: dict) -> tuple[str, str]:
    title = clean_text(record.get("title"))
    content_rating = clean_text(record.get("contentRating"))
    text = clean_text(" ".join([title, clean_text(record.get("summary")), clean_text(record.get("description"))]))
    if any(re.search(pattern, content_rating, re.IGNORECASE) for pattern in AGE_TRUE_PATTERNS):
        return "True", "app-store rating only"
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in AGE_TRUE_PATTERNS):
        return "True", "unknown"
    if content_rating:
        return "False", "none"
    return "unknown", "unknown"


def _login_from_metadata(record: dict) -> tuple[str, str]:
    text = content_blob(record)
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in LOGIN_FALSE_PATTERNS):
        return "False", "none"
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in LOGIN_TRUE_PATTERNS):
        return "True", "unknown"
    return "unknown", "unknown"


def evaluate_metadata_fields(record: dict, classification: dict) -> dict:
    text = content_blob(record)
    title_key = normalize_key(record.get("title"))
    currency = format_currency(record.get("currency"))
    iap_range = clean_text(record.get("IAPRange"))
    offers_iap = record.get("offersIAP")
    is_free = bool(record.get("free"))

    notes: list[str] = []

    languages_supported = detect_languages(record.get("languages"))
    if languages_supported != "unknown":
        notes.append("Platform language list is available in metadata.")

    age_required, age_method = _age_gate(record)
    if age_required == "True":
        notes.append(f"Age gate inferred from content rating or 17+/18+ language ({age_method}).")

    login_required, login_methods = _login_from_metadata(record)
    if login_required == "True":
        notes.append("Metadata references sign-in or account creation.")

    subscription_features = _extract_subscription_features(text)
    subscription_cost = extract_price_from_text(text, currency)

    if subscription_cost == "unknown" and iap_range:
        subscription_cost = iap_range_to_text(iap_range, currency)

    subscription_required_for_long_chat = "unknown"
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in LIMIT_PATTERNS):
        subscription_required_for_long_chat = "True"
        notes.append("Metadata mentions premium access, usage limits, or consumable credits.")
    elif not iap_range and offers_iap in (False, None) and subscription_features == "none" and is_free:
        subscription_required_for_long_chat = "False"
    elif not is_free and offers_iap in (False, None):
        subscription_required_for_long_chat = "False"

    all_features_available_without_subscription = "unknown"
    if subscription_features == "none" and not iap_range and offers_iap in (False, None):
        all_features_available_without_subscription = "True"
    elif subscription_features != "none" or iap_range or offers_iap:
        all_features_available_without_subscription = "False"

    if subscription_cost == "unknown" and subscription_features == "none" and not iap_range and offers_iap in (False, None):
        subscription_cost = "none"

    if subscription_features == "none" and (iap_range or offers_iap):
        subscription_features = "unknown"

    if subscription_features == "none" and subscription_cost == "none":
        notes.append("No subscription signal found in metadata.")
    elif subscription_features not in {"none", "unknown"}:
        notes.append(f"Metadata mentions premium features: {subscription_features}.")

    override = KNOWN_SUBSCRIPTION_OVERRIDES.get(title_key)
    if override:
        subscription_cost = override["subscription_cost"]
        subscription_features = override["subscription_features"]
        subscription_required_for_long_chat = override["subscription_required_for_long_chat"]
        all_features_available_without_subscription = override["all_features_available_without_subscription"]
        notes.append("Known platform override applied for pricing and free-tier interpretation.")

    confidence = "high" if classification["classification_confidence"] == "high" else "medium"
    if any(value == "unknown" for value in [languages_supported, login_required, age_required, subscription_required_for_long_chat]):
        confidence = "medium" if confidence == "high" else confidence

    return {
        "web_accessible": "unknown",
        "web_url": "null",
        "login_required": login_required,
        "login_methods": login_methods,
        "age_verification_required": age_required,
        "age_verification_method": age_method if age_required != "False" else "none",
        "subscription_required_for_long_chat": subscription_required_for_long_chat,
        "all_features_available_without_subscription": all_features_available_without_subscription,
        "subscription_features": subscription_features,
        "subscription_cost": subscription_cost,
        "languages_supported": languages_supported,
        "metadata_note": clip_note(" ".join(notes)),
        "metadata_confidence": confidence,
    }

