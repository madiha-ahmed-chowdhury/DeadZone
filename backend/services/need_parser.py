"""Bangla "need broadcast" parser.

Recognises messages of the shape ``<need> দরকার, <location>`` — e.g.
``পানি দরকার, মিরপুর ১০`` — plus a few natural variants and English
fallbacks. Extracts the free-text need description and trailing place
string, classifies the need into one of the coordinator-dashboard
categories (water / food / medical / shelter / other), flags urgency
keywords, and produces a 1-5 priority score.

Deliberately separate from ``pulse_parser`` (the "I'm alive" parser) even
though the shapes rhyme: an alive pulse and a need report are different
message intents, and keeping the phrase lists apart avoids one feature's
vocabulary silently swallowing the other's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Trailing "need" indicator words/phrases, most specific first is not
# required here — find_need_indicator() picks whichever occurs earliest.
NEED_INDICATORS: Tuple[str, ...] = (
    "দরকার",
    "প্রয়োজন",
    "লাগবে",
    "চাই",
    "need",
    "needed",
    "require",
)

# category -> keywords that identify it. Checked in this order, so a more
# specific phrase (e.g. "খাবার পানি") should be listed ahead of a broader
# one only where it changes the outcome — here "পানি" alone is enough since
# any mention of water should route to the water category.
CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "medical": (
        "ঔষধ", "ওষুধ", "মেডিসিন", "ডাক্তার", "চিকিৎসা", "হাসপাতাল",
        "ইনসুলিন", "স্যালাইন", "medicine", "doctor", "medical", "hospital",
    ),
    "water": (
        "খাবার পানি", "বিশুদ্ধ পানি", "পানি", "water",
    ),
    "food": (
        "খাবার", "খাদ্য", "চাল", "food", "rice",
    ),
    "shelter": (
        "আশ্রয়", "থাকার জায়গা", "তাঁবু", "ঘর", "shelter", "tent",
    ),
}

# Presence of any of these bumps the priority score up a notch — used to
# surface reports mentioning children, the elderly, pregnancy, or explicit
# emergency language above routine requests in the same category.
URGENCY_KEYWORDS: Tuple[str, ...] = (
    "জরুরি", "গুরুতর", "মুমূর্ষু", "শিশু", "গর্ভবতী", "বৃদ্ধ",
    "urgent", "emergency", "critical", "dying",
)

# Base priority per category (1 = lowest, 5 = highest). Medical need
# generally outranks food/shelter in crisis triage; "other" sits lowest
# since it's an unclassified catch-all.
BASE_PRIORITY: Dict[str, int] = {
    "medical": 5,
    "water": 4,
    "food": 3,
    "shelter": 3,
    "other": 2,
}

_SEPARATOR_RE = re.compile(
    r"\s*[\,\-\u2013\u2014:।\u09FA\(\)]\s*",  # , - – — : । ৺ ( )
    flags=re.UNICODE,
)
_PUNCT_TRIM_RE = re.compile(r"^[\s\.,;:।\u09FA\-]+|[\s\.,;:।\u09FA\-]+$")


@dataclass(frozen=True)
class ParsedNeed:
    """Structured result of parsing one Bangla need-broadcast message."""

    need_text: str              # free-text need description, e.g. "পানি"
    category: str                # water | food | medical | shelter | other
    place_text: Optional[str]
    priority: int                 # 1 (low) .. 5 (high)
    urgent: bool
    raw_text: str


def _normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def find_need_indicator(text: str) -> Optional[Tuple[str, int, int]]:
    """Return (indicator, start, end) of the earliest need-word match."""
    lower = (text or "").lower()
    best: Optional[Tuple[str, int, int]] = None
    for word in NEED_INDICATORS:
        idx = lower.find(word.lower())
        if idx != -1 and (best is None or idx < best[1]):
            best = (word, idx, idx + len(word))
    return best


def classify(need_text: str) -> str:
    """Map a free-text need description to a coordinator-facing category."""
    lower = (need_text or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                return category
    return "other"


def _is_urgent(text: str) -> bool:
    lower = (text or "").lower()
    return any(kw.lower() in lower for kw in URGENCY_KEYWORDS)


def score_priority(category: str, urgent: bool) -> int:
    base = BASE_PRIORITY.get(category, BASE_PRIORITY["other"])
    return min(5, base + 1) if urgent else base


def extract_place(text: str, indicator_end: int) -> Optional[str]:
    """Pull the place string following the need indicator, same heuristic
    as ``pulse_parser.extract_place``: stop at the next separator or
    sentence-end punctuation."""
    tail = text[indicator_end:].lstrip()
    if not tail:
        return None

    match = _SEPARATOR_RE.match(tail)
    if match:
        rest = tail[match.end():]
        stop = re.search(r"[\u09FA।\.](?:\s|$)", rest)
        if stop:
            rest = rest[: stop.start()]
        return _normalize(_PUNCT_TRIM_RE.sub("", rest)) or None

    stop = re.search(r"[\u09FA।\.]", tail)
    candidate = tail[: stop.start()] if stop else tail
    return _normalize(_PUNCT_TRIM_RE.sub("", candidate)) or None


def parse_need(raw_text: str) -> Optional[ParsedNeed]:
    """Parse one raw message into a :class:`ParsedNeed`, or ``None`` if it
    doesn't look like a need report at all."""
    if not raw_text:
        return None
    text = raw_text.strip()
    if not text:
        return None

    found = find_need_indicator(text)
    if not found:
        return None

    indicator, start, end = found
    need_text = _normalize(_PUNCT_TRIM_RE.sub("", text[:start]))
    if not need_text:
        # A bare "দরকার" with nothing describing what's needed isn't
        # actionable — don't manufacture a category out of nothing.
        return None

    place = extract_place(text, end)
    category = classify(need_text)
    urgent = _is_urgent(text)
    priority = score_priority(category, urgent)

    return ParsedNeed(
        need_text=need_text,
        category=category,
        place_text=place,
        priority=priority,
        urgent=urgent,
        raw_text=text,
    )


def _smoke() -> List[ParsedNeed]:  # pragma: no cover - dev helper
    samples = [
        "পানি দরকার, মিরপুর ১০",
        "শুকনো খাবার প্রয়োজন - উত্তরা",
        "জরুরি ঔষধ লাগবে, সিলেট",
        "একটা তাঁবু চাই, কক্সবাজার",
        "আমি ঠিক আছি, ঢাকা",             # should NOT match (alive pulse)
        "আজকের আবহাওয়া ভালো",              # should NOT match
    ]
    return [p for p in (parse_need(s) for s in samples) if p]


if __name__ == "__main__":  # pragma: no cover
    for p in _smoke():
        print(p)
