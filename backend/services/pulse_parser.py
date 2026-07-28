"""Bangla "I'm alive" pulse parser.

Recognises the canonical alive phrases plus a handful of natural variants,
extracts the trailing place string, and returns a structured record.

The parser is intentionally permissive: anything that *looks like* an alive
signal with a place attached is accepted.  The geocoder decides what to do
with the place text downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


# Bangla "I'm alive" phrases, ordered from most to least specific.
# Adding more variants? Append here — the parser is regex-driven.
ALIVE_PHRASES: Tuple[str, ...] = (
    "আমি ঠিক আছি",
    "আমি বেঁচে আছি",
    "আমি সুস্থ আছি",
    "আমি নিরাপদ আছি",
    "আমি বিপদে নেই",
    "I'm alive",
    "I am alive",
    "im alive",
    "safe",
)


# Optional location connective words that people often use in Bangla,
# e.g. "...আছি, ঢাকা" or "...আছি - সিলেট" or "...আছি (মিরপুর ১০)".
_SEPARATOR_RE = re.compile(
    r"\s*[\,\-\u2013\u2014:।\u09FA\(\)]\s*",  # , - – — : । ৺ ( )
    flags=re.UNICODE,
)

# Strip common trailing/leading politeness so the place string is clean
_PUNCT_TRIM_RE = re.compile(r"^[\s\.,;:।\u09FA\-]+|[\s\.,;:।\u09FA\-]+$")


@dataclass(frozen=True)
class ParsedPulse:
    """Structured result of parsing one Bangla message."""

    matched_phrase: str           # canonical phrase we matched against
    place_text: Optional[str]     # trimmed place string (or None)
    raw_text: str                 # original input, verbatim


def _normalize(text: str) -> str:
    """Collapse whitespace and strip common Unicode quirks."""
    if not text:
        return ""
    # Collapse any run of whitespace (including NBSP) into a single space.
    return re.sub(r"\s+", " ", text).strip()


def find_alive_phrase(text: str) -> Optional[Tuple[str, int, int]]:
    """Return (phrase, start, end) of the first alive match in *text*.

    Case-insensitive match.  Returns ``None`` if nothing matches.
    """
    haystack = text or ""
    lower = haystack.lower()
    for phrase in ALIVE_PHRASES:
        idx = lower.find(phrase.lower())
        if idx != -1:
            return phrase, idx, idx + len(phrase)
    return None


def extract_place(text: str, phrase_end: int) -> Optional[str]:
    """Pull the place string from *text* following the alive phrase.

    Heuristics:
      * If a separator (`, - — : । ( )`) immediately follows the phrase, the
        text up to the next separator or end-of-string is treated as the place.
      * Otherwise the remainder of the string is treated as the place.
      * The result is trimmed and returned, or ``None`` if empty.
    """
    tail = text[phrase_end:]
    tail = tail.lstrip()

    if not tail:
        return None

    # Look for the first explicit separator after the phrase
    match = _SEPARATOR_RE.match(tail)
    if match:
        # Skip the separator and capture the next segment
        rest = tail[match.end():]
        # Stop at the next separator that delimits a sentence end
        stop_match = re.search(r"[\u09FA।\.](?:\s|$)", rest)
        if stop_match:
            rest = rest[: stop_match.start()]
        return _normalize(_PUNCT_TRIM_RE.sub("", rest)) or None

    # No separator: take whatever is left, cut at the first sentence-stop.
    stop_match = re.search(r"[\u09FA।\.]", tail)
    candidate = tail[: stop_match.start()] if stop_match else tail
    candidate = _PUNCT_TRIM_RE.sub("", candidate)
    return _normalize(candidate) or None


def parse_pulse(raw_text: str) -> Optional[ParsedPulse]:
    """Parse one raw message into a :class:`ParsedPulse`.

    Returns ``None`` if the message doesn't look like an alive pulse.
    """
    if not raw_text:
        return None
    text = raw_text.strip()
    if not text:
        return None

    found = find_alive_phrase(text)
    if not found:
        return None

    phrase, _start, end = found
    place = extract_place(text, end)
    return ParsedPulse(matched_phrase=phrase, place_text=place, raw_text=text)


# ---------------------------------------------------------
# Small smoke-test helper
# ---------------------------------------------------------
def _smoke() -> List[ParsedPulse]:  # pragma: no cover - dev helper
    samples = [
        "আমি ঠিক আছি, ঢাকা",
        "আমি ঠিক আছি - মিরপুর ১০",
        "আমি সুস্থ আছি (চট্টগ্রাম)",
        "আমি ঠিক আছি। সিলেট",
        "আমি বেঁচে আছি: খুলনা বিভাগ",
        "আমি ঠিক আছি",
        "আজকের আবহাওয়া ভালো",          # should NOT match
    ]
    return [p for p in (parse_pulse(s) for s in samples) if p]


if __name__ == "__main__":  # pragma: no cover
    for p in _smoke():
        print(p)