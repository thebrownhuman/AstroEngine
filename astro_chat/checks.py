"""Compare graha-sign and graha-house statements in a reply with the chart."""

from __future__ import annotations

import re

GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
SIGNS = {
    "mesha": "Mesha", "aries": "Mesha", "vrishabha": "Vrishabha", "taurus": "Vrishabha",
    "mithuna": "Mithuna", "gemini": "Mithuna", "karka": "Karka", "cancer": "Karka",
    "simha": "Simha", "leo": "Simha", "kanya": "Kanya", "virgo": "Kanya",
    "tula": "Tula", "libra": "Tula", "vrischika": "Vrischika", "scorpio": "Vrischika",
    "dhanu": "Dhanu", "sagittarius": "Dhanu", "makara": "Makara", "capricorn": "Makara",
    "kumbha": "Kumbha", "aquarius": "Kumbha", "meena": "Meena", "pisces": "Meena",
}
_G = "|".join(GRAHAS)
_S = "|".join(SIGNS)
_SIGN_RE = re.compile(r"\b(" + _G + r")\b(?:\s+is)?\s+in\s+(" + _S + r")\b", re.I)
_HOUSE_RE = re.compile(r"\b(" + _G + r")\b(?:\s+is)?\s+in\s+(?:the\s+)?(\d{1,2})"
                       r"(?:st|nd|rd|th)\s+house", re.I)


def check_reply(reply: str, placements: dict[str, dict]) -> list[dict]:
    found, seen = [], set()
    for kind, regex, norm in (("sign", _SIGN_RE, lambda s: SIGNS[s.lower()]),
                              ("house", _HOUSE_RE, int)):
        for m in regex.finditer(reply):
            graha, claimed = m.group(1).title(), norm(m.group(2))
            actual = placements.get(graha, {}).get(kind)
            if actual is None or (graha, kind, claimed) in seen:
                continue
            seen.add((graha, kind, claimed))
            found.append({"graha": graha, "kind": kind, "claimed": claimed,
                          "actual": actual, "ok": claimed == actual})
    return found
