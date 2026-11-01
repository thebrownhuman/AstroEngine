"""The rule condition language, evaluated against the engine's chart JSON.

A condition is a mapping. Most keys test one "subject" graha, which the rule
binds first with ``lord_of`` (the lord of a house) or ``planet`` (a named
graha). Keys in one mapping are ANDed; ``all``, ``any`` and ``not`` combine
nested conditions.

    lord_of: 1-12              bind the subject to that house's lord
    planet: Sun..Ketu          bind the subject to a named graha
    in_house: n | [n, ...]     subject's whole-sign house from the Lagna
    in_sign: name | index      subject's rashi (Sanskrit, English or 0-11)
    dignity: s | [s, ...]      exalted, debilitated, moolatrikona, own_sign, neutral
    nature: benefic | malefic  subject's BPHS nature (Ch.3 v11, as the engine reports it)
    conjunct: target           another graha in the subject's sign
    aspected_by: target        another graha casting graha drishti on the subject
    associated_with: target    conjunct or aspected_by (BPHS "related to")
    yoga_present: name         the engine's yoga report has that yoga
    dasha_lord: target         the running mahadasha lord matches
    all / any: [cond, ...]     combinators
    not: cond                  negation

A target is a graha name, ``benefic``, ``malefic`` or ``subject``.

Nothing here computes astrology: every test reads a field the engine already
returns, and each one that passes leaves an evidence entry naming that field.
"""

from __future__ import annotations

GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
DIGNITIES = ("exalted", "debilitated", "moolatrikona", "own_sign", "neutral")
NATURES = ("benefic", "malefic")
TARGETS = GRAHAS + NATURES

SUBJECT_KEYS = {"in_house", "in_sign", "dignity", "nature", "conjunct",
                "aspected_by", "associated_with"}
BINDING_KEYS = {"lord_of", "planet"}
COMBINATORS = {"all", "any", "not"}
OTHER_KEYS = {"yoga_present", "dasha_lord"}
KEYS = SUBJECT_KEYS | BINDING_KEYS | COMBINATORS | OTHER_KEYS


class ConditionError(ValueError):
    """A condition that does not follow the language above."""


def validate(cond, bound: bool = False, where: str = "when") -> None:
    """Raise ConditionError unless ``cond`` is well formed.

    ``bound`` says whether an enclosing condition already bound a subject.
    """
    if not isinstance(cond, dict) or not cond:
        raise ConditionError(f"{where}: a condition is a non-empty mapping")
    unknown = set(cond) - KEYS
    if unknown:
        raise ConditionError(f"{where}: unknown keys {sorted(unknown)}")
    if len(set(cond) & BINDING_KEYS) > 1:
        raise ConditionError(f"{where}: use lord_of or planet, not both")
    if "lord_of" in cond and cond["lord_of"] not in range(1, 13):
        raise ConditionError(f"{where}: lord_of must be a house 1-12")
    if "planet" in cond and cond["planet"] not in GRAHAS:
        raise ConditionError(f"{where}: unknown planet {cond['planet']!r}")
    bound = bound or bool(set(cond) & BINDING_KEYS)
    if set(cond) & SUBJECT_KEYS and not bound:
        raise ConditionError(f"{where}: {sorted(set(cond) & SUBJECT_KEYS)} need lord_of or planet")
    if "in_house" in cond:
        houses = cond["in_house"] if isinstance(cond["in_house"], list) else [cond["in_house"]]
        if not houses or any(h not in range(1, 13) for h in houses):
            raise ConditionError(f"{where}: in_house must be 1-12")
    if "dignity" in cond:
        states = cond["dignity"] if isinstance(cond["dignity"], list) else [cond["dignity"]]
        if any(s not in DIGNITIES for s in states):
            raise ConditionError(f"{where}: dignity must be one of {DIGNITIES}")
    if "nature" in cond and cond["nature"] not in NATURES:
        raise ConditionError(f"{where}: nature must be benefic or malefic")
    for key in ("conjunct", "aspected_by", "associated_with"):
        if key in cond and cond[key] not in TARGETS:
            raise ConditionError(f"{where}: {key} target must be one of {TARGETS}")
    if "dasha_lord" in cond and cond["dasha_lord"] not in GRAHAS + ("subject",):
        raise ConditionError(f"{where}: dasha_lord must be a graha or 'subject'")
    if cond.get("dasha_lord") == "subject" and not bound:
        raise ConditionError(f"{where}: dasha_lord 'subject' needs lord_of or planet")
    for key in ("all", "any"):
        if key in cond:
            if not isinstance(cond[key], list) or not cond[key]:
                raise ConditionError(f"{where}.{key}: needs a non-empty list")
            for i, sub in enumerate(cond[key]):
                validate(sub, bound, f"{where}.{key}[{i}]")
    if "not" in cond:
        validate(cond["not"], bound, f"{where}.not")


def _matches(graha: dict, target: str) -> bool:
    if target in NATURES:
        return graha["bphs_nature"] == target
    return graha["name"] == target


def _sign_matches(graha: dict, sign) -> bool:
    if isinstance(sign, int):
        return graha["sign_index"] == sign
    return sign in (graha["sign"], graha["sign_en"])


def _conjunct(chart: dict, subject: str, target: str) -> list[str]:
    grahas = chart["grahas"]
    sign = grahas[subject]["sign_index"]
    return [n for n, g in grahas.items()
            if n != subject and g["sign_index"] == sign and _matches(g, target)]


def _aspecting(chart: dict, subject: str, target: str) -> list[str]:
    grahas = chart["grahas"]
    return [a["graha"] for a in chart["aspects"]
            if a["graha"] != subject and subject in a["aspects_grahas"]
            and _matches(grahas[a["graha"]], target)]


def _yoga_names(chart: dict) -> list[str]:
    report = chart.get("yogas") or {}
    return [y["name"] for group in report.get("yoga_details", [])
            for y in group.get("yoga_list", []) if y.get("has_yoga")]


def _mahadasha_lord(chart: dict) -> str | None:
    chain = (chart.get("current_dasha") or {}).get("chain") or []
    return chain[0]["lord"] if chain else None


def evaluate(cond: dict, chart: dict, subject: str | None = None) -> tuple[bool, list[dict]]:
    """Return (passed, evidence). Evidence is only meaningful when passed."""
    evidence: list[dict] = []

    def fact(text: str, field: str, value) -> None:
        evidence.append({"fact": text, "field": field, "value": value})

    if "lord_of" in cond:
        house = cond["lord_of"]
        subject = chart["houses"][house - 1]["lord"]
        fact(f"{subject} is lord of house {house}", f"houses[{house - 1}].lord", subject)
    elif "planet" in cond:
        subject = cond["planet"]

    g = chart["grahas"][subject] if subject else None

    if "in_house" in cond:
        want = cond["in_house"] if isinstance(cond["in_house"], list) else [cond["in_house"]]
        if g["house"] not in want:
            return False, []
        fact(f"{subject} is in house {g['house']}", f"grahas.{subject}.house", g["house"])
    if "in_sign" in cond:
        if not _sign_matches(g, cond["in_sign"]):
            return False, []
        fact(f"{subject} is in {g['sign_en']}", f"grahas.{subject}.sign", g["sign"])
    if "dignity" in cond:
        want = cond["dignity"] if isinstance(cond["dignity"], list) else [cond["dignity"]]
        state = g["dignity"]["state"]
        if state not in want:
            return False, []
        fact(f"{subject} is {state}", f"grahas.{subject}.dignity.state", state)
    if "nature" in cond:
        if g["bphs_nature"] != cond["nature"]:
            return False, []
        fact(f"{subject} is a {g['bphs_nature']}", f"grahas.{subject}.bphs_nature", g["bphs_nature"])
    if "conjunct" in cond:
        hits = _conjunct(chart, subject, cond["conjunct"])
        if not hits:
            return False, []
        fact(f"{subject} is conjunct {', '.join(hits)}", f"houses[{g['house'] - 1}].occupants", hits)
    if "aspected_by" in cond:
        hits = _aspecting(chart, subject, cond["aspected_by"])
        if not hits:
            return False, []
        fact(f"{subject} is aspected by {', '.join(hits)}", "aspects[].aspects_grahas", hits)
    if "associated_with" in cond:
        target = cond["associated_with"]
        joined, seen = _conjunct(chart, subject, target), _aspecting(chart, subject, target)
        if not joined and not seen:
            return False, []
        if joined:
            fact(f"{subject} is conjunct {', '.join(joined)}", f"houses[{g['house'] - 1}].occupants", joined)
        if seen:
            fact(f"{subject} is aspected by {', '.join(seen)}", "aspects[].aspects_grahas", seen)
    if "yoga_present" in cond:
        if cond["yoga_present"] not in _yoga_names(chart):
            return False, []
        fact(f"{cond['yoga_present']} is present", "yogas.yoga_details[].yoga_list[].has_yoga", True)
    if "dasha_lord" in cond:
        want = subject if cond["dasha_lord"] == "subject" else cond["dasha_lord"]
        lord = _mahadasha_lord(chart)
        if lord is None or lord != want:
            return False, []
        fact(f"{lord} mahadasha is running", "current_dasha.chain[0].lord", lord)
    if "all" in cond:
        for sub in cond["all"]:
            ok, ev = evaluate(sub, chart, subject)
            if not ok:
                return False, []
            evidence += ev
    if "any" in cond:
        for sub in cond["any"]:
            ok, ev = evaluate(sub, chart, subject)
            if ok:
                evidence += ev
                break
        else:
            return False, []
    if "not" in cond:
        ok, _ = evaluate(cond["not"], chart, subject)
        if ok:
            return False, []
        fact(f"not ({describe(cond['not'])})", "-", False)
    return True, evidence


def describe(cond: dict) -> str:
    """A short human-readable rendering of a condition, for evidence text."""
    parts = []
    for key, value in cond.items():
        if key in ("all", "any"):
            parts.append(f"{key}(" + "; ".join(describe(c) for c in value) + ")")
        elif key == "not":
            parts.append(f"not ({describe(value)})")
        else:
            parts.append(f"{key} {value}")
    return ", ".join(parts)
