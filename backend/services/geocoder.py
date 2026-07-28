"""Static Bangla place-name gazetteer for the MVP.

The MVP doesn't pull in a full geocoder (no Nominatim, no Google Places) —
that would slow the response and add a hard dependency on an external
service during a crisis.  Instead we ship a curated list of the most common
cities, divisions, and thetas that people report from during Bangladesh
crises, and fall back to a national centroid when the place is unknown.

Each entry maps one or more Bangla aliases (or Latin spellings) to a
canonical name + lat/lng centroid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Place:
    """A geocoded place with its canonical name and centroid."""

    canonical: str
    lat: float
    lng: float
    aliases: Tuple[str, ...]


# Bangladesh national centroid (used when we recognise a Bangla place string
# but can't pinpoint it further — better than dropping the signal entirely).
NATIONAL_CENTROID = Place(
    canonical="Bangladesh (centroid)",
    lat=23.685,
    lng=90.3563,
    aliases=(),
)


# A small, opinionated gazetteer. Aliases are lowercased before matching.
# Coordinates are approximate centroids; they don't need to be exact for an
# h3 resolution-7 hex (~5 km²) visualisation.
GAZETTEER: Tuple[Place, ...] = (
    Place("Dhaka",     23.8103,  90.4125, ("dhaka", "ঢাকা")),
    Place("Mirpur 10", 23.8069,  90.3687, ("mirpur 10", "mirpur-10", "mirpur", "মিরপুর ১০", "মিরপুর")),
    Place("Mirpur 11", 23.8156,  90.3667, ("mirpur 11", "মিরপুর ১১")),
    Place("Mirpur 12", 23.8217,  90.3654, ("mirpur 12", "মিরপুর ১২")),
    Place("Uttara",    23.8759,  90.3795, ("uttara", "উত্তরা")),
    Place("Dhanmondi", 23.7461,  90.3742, ("dhanmondi", "ধানমন্ডি")),
    Place("Mohammadpur", 23.7600, 90.3597, ("mohammadpur", "মোহাম্মদপুর")),
    Place("Old Dhaka", 23.7100,  90.4070, ("old dhaka", "পুরান ঢাকা")),
    Place("Chattogram", 22.3569, 91.7832, ("chattogram", "chittagong", "চট্টগ্রাম", "চিটাগাং")),
    Place("Sylhet",     24.8949, 91.8687, ("sylhet", "সিলেট")),
    Place("Khulna",     22.8456, 89.5403, ("khulna", "খুলনা")),
    Place("Rajshahi",   24.3745, 88.6042, ("rajshahi", "রাজশাহী")),
    Place("Barishal",   22.7010, 90.3535, ("barishal", "barisal", "বরিশাল")),
    Place("Rangpur",    25.7439, 89.2752, ("rangpur", "রংপুর")),
    Place("Mymensingh", 24.7471, 90.4203, ("mymensingh", "ময়মনসিংহ")),
    Place("Comilla",    23.4607, 91.1809, ("comilla", "cumilla", "কুমিল্লা")),
    Place("Narayanganj", 23.6238, 90.4996, ("narayanganj", "নারায়ণগঞ্জ")),
    Place("Gazipur",    23.9999, 90.4203, ("gazipur", "গাজীপুর")),
    Place("Tangail",    24.2513, 89.9167, ("tangail", "টাঙ্গাইল")),
    Place("Jessore",    23.1667, 89.2167, ("jessore", "যশোর")),
    Place("Bogura",     24.8465, 89.3776, ("bogura", "bogra", "বগুড়া")),
    Place("Cox's Bazar", 21.4272, 92.0678, ("cox's bazar", "coxs bazar", "cox bazar", "কক্সবাজার")),
    Place("Bandarban",  22.1953, 92.2184, ("bandarban", "বান্দরবান")),
    Place("Rangamati",  22.7324, 92.2985, ("rangamati", "রাঙামাটি")),
    Place("Khagrachari", 23.1193, 91.9847, ("khagrachari", "খাগড়াছড়ি")),
    Place("Feni",       23.0144, 91.3966, ("feni", "ফেনী")),
    Place("Noakhali",   22.8240, 91.0974, ("noakhali", "নোয়াখালী")),
    Place("Habiganj",   24.3745, 91.4156, ("habiganj", "হবিগঞ্জ")),
    Place("Moulvibazar", 24.4821, 91.7774, ("moulvibazar", "মৌলভীবাজার")),
    Place("Sunamganj",  25.0658, 91.3950, ("sunamganj", "সুনামগঞ্জ")),
    Place("Kishoreganj", 24.4331, 90.7866, ("kishoreganj", "কিশোরগঞ্জ")),
    Place("Netrokona",  24.8835, 90.7275, ("netrokona", "নেত্রকোনা")),
    Place("Sherpur",    25.0188, 90.0094, ("sherpur", "শেরপুর")),
    Place("Jamalpur",   24.9377, 89.9375, ("jamalpur", "জামালপুর")),
    Place("Chandpur",   23.2333, 90.6500, ("chandpur", "চাঁদপুর")),
    Place("Lakshmipur", 22.9447, 90.8262, ("lakshmipur", "লক্ষ্মীপুর")),
    Place("Brahmanbaria", 23.9571, 91.1116, ("brahmanbaria", "ব্রাহ্মণবাড়িয়া")),
    Place("Narsingdi",  23.9320, 90.7150, ("narsingdi", "নরসিংদী")),
    Place("Munshiganj", 23.5422, 90.5305, ("munshiganj", "মুন্সিগঞ্জ")),
    Place("Manikganj",  23.8617, 90.0003, ("manikganj", "মানিকগঞ্জ")),
    Place("Faridpur",   23.6070, 89.8429, ("faridpur", "ফরিদপুর")),
    Place("Rajbari",    23.7574, 89.6444, ("rajbari", "রাজবাড়ী")),
    Place("Madaripur",  23.1642, 90.1897, ("madaripur", "মাদারীপুর")),
    Place("Shariatpur", 23.2053, 90.3461, ("shariatpur", "শরীয়তপুর")),
    Place("Gopalganj",  23.0050, 89.8266, ("gopalganj", "গোপালগঞ্জ")),
    Place("Pirojpur",   22.5841, 89.9750, ("pirojpur", "পিরোজপুর")),
    Place("Jhalokati",  22.6411, 90.2000, ("jhalokati", "ঝালকাঠি")),
    Place("Barguna",    22.1593, 90.1194, ("barguna", "বরগুনা")),
    Place("Patuakhali", 22.3596, 90.3297, ("patuakhali", "পটুয়াখালী")),
    Place("Bhola",      22.6850, 90.6500, ("bhola", "ভোলা")),
    Place("Satkhira",   22.7185, 89.0705, ("satkhirä", "satkhira", "সাতক্ষীরা")),
    Place("Bagerhat",   22.6602, 89.7855, ("bagerhat", "বাগেরহাট")),
    Place("Narail",     23.1727, 89.5120, ("narail", "নড়াইল")),
    Place("Magura",     23.4854, 89.4198, ("magura", "মাগুরা")),
    Place("Chuadanga",  23.6393, 88.8419, ("chuadanga", "চুয়াডাঙ্গা")),
    Place("Meherpur",   23.7768, 88.6353, ("meherpur", "মেহেরপুর")),
    Place("Kushtia",    23.9072, 89.1194, ("kushtia", "কুষ্টিয়া")),
    Place("Pabna",      23.9988, 89.2333, ("pabna", "পাবনা")),
    Place("Sirajganj",  24.4533, 89.7006, ("sirajganj", "সিরাজগঞ্জ")),
    Place("Naogaon",    24.7938, 88.9318, ("naogaon", "নওগাঁ")),
    Place("Natore",     24.4206, 89.0003, ("natore", "নাটোর")),
    Place("Chapainawabganj", 24.5967, 88.2775, ("chapainawabganj", "চাঁপাইনবাবগঞ্জ")),
    Place("Joypurhat",  25.0947, 89.0947, ("joypurhat", "জয়পুরহাট")),
    Place("Thakurgaon", 26.0336, 88.4664, ("thakurgaon", "ঠাকুরগাঁও")),
    Place("Dinajpur",   25.6279, 88.6332, ("dinajpur", "দিনাজপুর")),
    Place("Kurigram",   25.8054, 89.6362, ("kurigram", "কুড়িগ্রাম")),
    Place("Gaibandha",  25.3333, 89.5333, ("gaibandha", "গাইবান্ধা")),
    Place("Lalmonirhat", 25.9923, 89.2847, ("lalmonirhat", "লালমনিরহাট")),
    Place("Nilphamari", 25.9318, 88.8560, ("nilphamari", "নীলফামারী")),
    Place("Panchagarh", 26.3411, 88.5541, ("panchagarh", "পঞ্চগড়")),
)


@dataclass(frozen=True)
class GeocodeResult:
    """Result of looking up a free-text place string."""

    lat: float
    lng: float
    canonical: str          # canonical place name (or "Bangladesh (centroid)")
    matched_alias: Optional[str]   # which alias matched (None = centroid fallback)
    confidence: str         # 'high' | 'medium' | 'low'


def _normalise(text: str) -> str:
    return (text or "").strip().lower()


def _iter_aliases(place: Place) -> Iterable[str]:
    return (a.lower() for a in place.aliases)


def geocode(place_text: Optional[str]) -> GeocodeResult:
    """Resolve a free-text place string to lat/lng.

    The match strategy:
      1. Exact alias match (case-insensitive, trimmed).
      2. Substring match — if an alias appears anywhere in the place string,
         the longer aliases win so "mirpur 10" beats "mirpur".
      3. Fall back to the national centroid with ``confidence='low'``.
    """
    if not place_text:
        return GeocodeResult(
            lat=NATIONAL_CENTROID.lat,
            lng=NATIONAL_CENTROID.lng,
            canonical=NATIONAL_CENTROID.canonical,
            matched_alias=None,
            confidence="low",
        )

    needle = _normalise(place_text)
    if not needle:
        return GeocodeResult(
            lat=NATIONAL_CENTROID.lat,
            lng=NATIONAL_CENTROID.lng,
            canonical=NATIONAL_CENTROID.canonical,
            matched_alias=None,
            confidence="low",
        )

    # 1. Exact match
    for place in GAZETTEER:
        for alias in _iter_aliases(place):
            if alias == needle:
                return GeocodeResult(
                    lat=place.lat,
                    lng=place.lng,
                    canonical=place.canonical,
                    matched_alias=alias,
                    confidence="high",
                )

    # 2. Substring match — prefer longer aliases so "mirpur 10" beats "mirpur"
    candidates: List[Tuple[int, Place, str]] = []
    for place in GAZETTEER:
        for alias in _iter_aliases(place):
            if alias and alias in needle:
                candidates.append((len(alias), place, alias))

    if candidates:
        candidates.sort(key=lambda t: t[0], reverse=True)
        _score, place, alias = candidates[0]
        return GeocodeResult(
            lat=place.lat,
            lng=place.lng,
            canonical=place.canonical,
            matched_alias=alias,
            confidence="medium",
        )

    # 3. National centroid fallback
    return GeocodeResult(
        lat=NATIONAL_CENTROID.lat,
        lng=NATIONAL_CENTROID.lng,
        canonical=NATIONAL_CENTROID.canonical,
        matched_alias=None,
        confidence="low",
    )


# Quick sanity check
def _smoke() -> Sequence[Tuple[str, GeocodeResult]]:  # pragma: no cover
    cases = [
        "ঢাকা",
        "ঢাকা শহর",
        "মিরপুর ১০",
        "Mirpur",
        "chattogram",
        "পটুয়াখালী সদর",
        "atlantis",                      # unknown
        "",                              # empty
    ]
    return [(t, geocode(t)) for t in cases]


if __name__ == "__main__":  # pragma: no cover
    for raw, result in _smoke():
        print(f"{raw!r:25} -> {result.canonical} ({result.confidence})")