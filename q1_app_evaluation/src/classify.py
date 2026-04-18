from __future__ import annotations

import re

from .utils import clean_text, clip_note, content_blob, extract_domain, normalize_key


# Explicit curated overrides for widely known assistant brands and repeated companion platforms.
TITLE_OVERRIDES = {
    "chatgpt": ("general_purpose", "Known broad LLM assistant brand."),
    "google gemini": ("general_purpose", "Known broad LLM assistant brand."),
    "claude by anthropic": ("general_purpose", "Known broad LLM assistant brand."),
    "microsoft copilot": ("general_purpose", "Known broad LLM assistant brand."),
    "grok ai chat video": ("general_purpose", "Known broad LLM assistant brand."),
    "deepseek ai assistant": ("general_purpose", "Known broad LLM assistant brand."),
    "perplexity ask anything": ("general_purpose", "Known broad LLM assistant brand."),
    "poe fast ai chat": ("general_purpose", "Known broad LLM assistant brand."),
    "pi your personal ai": ("general_purpose", "Known broad LLM assistant brand."),
    "meta ai assistant glasses": ("general_purpose", "Known broad LLM assistant brand."),
    "kindroid your personal ai": ("companion", "Known companion platform centered on personal AI relationships."),
    "character ai chat talk text": ("companion", "Known character-chat and roleplay platform."),
    "replika ai friend": ("companion", "Known AI companion platform focused on friendship and relationships."),
    "replika my ai friend": ("companion", "Known AI companion platform focused on friendship and relationships."),
    "polybuzz chat with characters": ("companion", "Known character-chat companion platform."),
    "polybuzz chat with ai friends": ("companion", "Known character-chat companion platform."),
    "chai social ai platform chat": ("companion", "Known user-created character and companion chat platform."),
    "chai chat ai platform": ("companion", "Known user-created character and companion chat platform."),
    "talkie creative ai community": ("companion", "Known character-chat community."),
    "dopple ai": ("companion", "Known AI character and roleplay platform."),
    "gauth ai study companion": ("other", "Task-specific homework and study helper."),
    "wysa mental wellbeing ai": ("other", "Wellness-focused app rather than companion or broad assistant."),
    "yourmove ai dating assistant": ("other", "Dating-helper tool, not an AI companion itself."),
    "rare ai dating assistant": ("other", "Dating-helper tool, not an AI companion itself."),
    "texting ai wingman": ("other", "Dating-helper tool, not an AI companion itself."),
    "animal boyfriend": ("other", "Dating simulator/game title rather than a broad AI companion or assistant."),
    "mystic messenger": ("other", "Narrative/messaging game rather than a general assistant."),
    "mechat interactive stories": ("other", "Interactive story app rather than a general assistant."),
    "talkie lab ai playground": ("general_purpose", "Markets a multi-model AI playground rather than relational chat."),
}

DOMAIN_GENERAL = {
    "openai.com",
    "chatgpt.com",
    "anthropic.com",
    "claude.ai",
    "gemini.google.com",
    "google.com",
    "copilot.microsoft.com",
    "microsoft.com",
    "grok.com",
    "x.ai",
    "perplexity.ai",
    "deepseek.com",
    "poe.com",
    "pi.ai",
}

DOMAIN_COMPANION = {
    "character.ai",
    "kindroid.ai",
    "replika.ai",
    "replika.com",
    "polybuzz.ai",
    "talkie-ai.com",
    "chai-research.com",
    "dotdotdot.chat",
    "hiwaifu.com",
    "rubii.ai",
    "roleplai.app",
    "flipped.chat",
}

COMPANION_HIGH = [
    r"\bboyfriend\b",
    r"\bgirlfriend\b",
    r"\bvirtual (?:ai )?(?:boyfriend|girlfriend|partner|friend)\b",
    r"\bai companion\b",
    r"\bsoulmate\b",
    r"\broleplay\b",
    r"\bcharacter ai\b",
    r"\bchat with characters\b",
    r"\bromantic\b",
    r"\brelationship\b",
    r"\bflirt",
    r"\bdating simulator\b",
    r"\bwaifu\b",
]

COMPANION_MEDIUM = [
    r"\bfriend\b",
    r"\bpartner\b",
    r"\bemotional support\b",
    r"\blonely|loneliness\b",
    r"\banime character\b",
    r"\bfantasy partner\b",
    r"\bai lover\b",
    r"\bai soulmate\b",
]

GENERAL_HIGH = [
    r"\bask anything\b",
    r"\bai assistant\b",
    r"\bmultimodal\b",
    r"\bproductivity\b",
    r"\bsearch\b",
    r"\bresearch\b",
    r"\bcoding\b",
    r"\bmodels like\b",
    r"\bdeepseek\b",
    r"\bclaude\b",
    r"\bchatgpt\b",
    r"\bgemini\b",
    r"\bcopilot\b",
]

TASK_HIGH = [
    r"\bstudy\b",
    r"\bhomework\b",
    r"\bmath\b",
    r"\btranslator\b",
    r"\btranslate\b",
    r"\bkeyboard\b",
    r"\bimage generator\b",
    r"\bphoto editor\b",
    r"\bessay writer\b",
    r"\bwriting assistant\b",
    r"\bpdf\b",
    r"\bdocument\b",
    r"\bcoding assistant\b",
    r"\bhoroscope\b",
    r"\btarot\b",
    r"\bfitness\b",
    r"\bmeditation\b",
    r"\bwellbeing\b",
    r"\bwellness\b",
    r"\bbrowser\b",
]

MIXED_HINTS = [
    r"\bassistant\b",
    r"\bproductivity\b",
    r"\bimage generation\b",
    r"\bgenerate images\b",
    r"\bwrite\b",
    r"\bsummarize\b",
    r"\bmultimodal\b",
    r"\btools\b",
    r"\bplayground\b",
]


def _count_matches(patterns: list[str], text: str, weight: int = 1) -> int:
    score = 0
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
    return score


def classify_app(record: dict) -> dict:
    title = clean_text(record.get("title"))
    title_key = normalize_key(title)
    domain = extract_domain(record.get("developerWebsite") or record.get("url"))
    text = content_blob(record).lower()

    if title_key in TITLE_OVERRIDES:
        app_type, note = TITLE_OVERRIDES[title_key]
        return {
            "app_type": app_type,
            "classification_note": clip_note(note),
            "classification_confidence": "high",
        }

    if any(domain.endswith(item) for item in DOMAIN_GENERAL):
        return {
            "app_type": "general_purpose",
            "classification_note": clip_note("Developer domain matches a known general-purpose assistant platform."),
            "classification_confidence": "high",
        }

    if any(domain.endswith(item) for item in DOMAIN_COMPANION):
        return {
            "app_type": "companion",
            "classification_note": clip_note("Developer domain matches a known companion or character-chat platform."),
            "classification_confidence": "high",
        }

    companion_score = _count_matches(COMPANION_HIGH, title, 3)
    companion_score += _count_matches(COMPANION_HIGH, text, 2)
    companion_score += _count_matches(COMPANION_MEDIUM, text, 1)

    general_score = _count_matches(GENERAL_HIGH, title, 3)
    general_score += _count_matches(GENERAL_HIGH, text, 2)

    task_score = _count_matches(TASK_HIGH, title, 3)
    task_score += _count_matches(TASK_HIGH, text, 2)

    mixed_score = _count_matches(MIXED_HINTS, text, 1)

    if task_score >= 6 and companion_score < 6:
        return {
            "app_type": "other",
            "classification_note": clip_note("Listing emphasizes a task-specific use case more than companionship or broad assistant behavior."),
            "classification_confidence": "medium",
        }

    if companion_score >= 8 and (general_score >= 4 or mixed_score >= 3):
        return {
            "app_type": "mixed",
            "classification_note": clip_note("Listing combines relationship or character-chat cues with broader assistant or tool functionality."),
            "classification_confidence": "medium",
        }

    if companion_score >= 8:
        return {
            "app_type": "companion",
            "classification_note": clip_note("Listing strongly emphasizes companion, roleplay, character chat, or relationship framing."),
            "classification_confidence": "medium",
        }

    if general_score >= 6 and task_score < 4:
        return {
            "app_type": "general_purpose",
            "classification_note": clip_note("Listing reads like a broad assistant rather than a companion app."),
            "classification_confidence": "medium",
        }

    if task_score >= 4:
        return {
            "app_type": "other",
            "classification_note": clip_note("Listing is more task-focused than companion-focused."),
            "classification_confidence": "medium",
        }

    if companion_score >= 4 and general_score >= 3:
        return {
            "app_type": "mixed",
            "classification_note": clip_note("Listing contains both companion signals and broader assistant/tool signals."),
            "classification_confidence": "low",
        }

    if companion_score >= 4:
        return {
            "app_type": "companion",
            "classification_note": clip_note("Listing contains meaningful companion or relationship signals."),
            "classification_confidence": "low",
        }

    if general_score >= 3:
        return {
            "app_type": "general_purpose",
            "classification_note": clip_note("Listing contains assistant-like signals but without a strong override."),
            "classification_confidence": "low",
        }

    return {
        "app_type": "other",
        "classification_note": clip_note("Fallback classification: not enough evidence for companion or broad assistant behavior."),
        "classification_confidence": "low",
    }

