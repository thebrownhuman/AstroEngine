"""Search hard for Daridra Yoga, over 39 charts, with bitmasks.

Fifteen charts could not tell twenty-seven candidate formulas apart. Twenty-
four discriminating charts later, all twenty-seven are dead: the rule is not
any one- or two-term formula over the house predicates tried.

Thirty-nine charts changes what a fit is worth. There are roughly 2e7 three-
term formulas over this predicate set, and the chance that a given one matches
39 independent verdicts by luck is 2**-39. Expected false positives across the
whole search are therefore about 1e-5 -- so unlike the fifteen-chart case,
anything that fits here is almost certainly the real rule rather than an
overfit. That is the whole reason for collecting the extra charts first.

Each predicate becomes one 39-bit integer, so a candidate is two or three
machine-word operations and the full space takes seconds instead of hours.

    python validation/search_daridra.py

Costs nothing: it replays charts already cached.
"""

from __future__ import annotations

import sys
from itertools import combinations

sys.path.insert(0, ".")
from astro_engine.constants import (  # noqa: E402
    NATURAL_BENEFICS, NATURAL_MALEFICS, SIGN_LORDS,
)
from validation.diagnose_yogas import load  # noqa: E402
from validation.parallel_fetch import cache_path  # noqa: E402
from validation.pin_daridra import (  # noqa: E402
    predicates as house_predicates, proposed_charts,
)

import json  # noqa: E402

DUSTHANAS = {6, 8, 12}
GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn",
          "Rahu", "Ketu")


def wide_predicates(chart: dict) -> dict[str, bool]:
    """The house-lord set, plus placements, conjunctions and dignities."""
    out = dict(house_predicates(chart))
    lagna = chart["lagna"]["sign_index"]
    grahas = chart["grahas"]

    for name in GRAHAS:
        if name not in grahas:
            continue
        body = grahas[name]
        for house in range(1, 13):
            out[f"{name}@{house}"] = body["house"] == house
        out[f"{name} dusthana"] = body["house"] in DUSTHANAS
        out[f"{name} retro"] = bool(body.get("is_retrograde"))

    # Where the 2nd and 11th lords stand relative to each other and to the
    # Lagna lord -- the classical wealth significators.
    for nth in (2, 11):
        lord = SIGN_LORDS[(lagna + nth - 1) % 12]
        out[f"{nth}L is lagna lord"] = lord == SIGN_LORDS[lagna]
        for other in (1, 2, 5, 6, 8, 9, 11, 12):
            other_lord = SIGN_LORDS[(lagna + other - 1) % 12]
            out[f"{nth}L with {other}L"] = (
                lord != other_lord
                and grahas[lord]["house"] == grahas[other_lord]["house"]
            )
        count = (grahas[lord]["house"] - 1) % 12 + 1
        for target in range(1, 13):
            out[f"{nth}L {target} from lagna"] = count == target
        out[f"{nth}L combust"] = (
            lord not in ("Sun", "Rahu", "Ketu")
            and grahas[lord]["house"] == grahas["Sun"]["house"]
        )
        out[f"{nth}L malefic-joined"] = any(
            m != lord and grahas[m]["house"] == grahas[lord]["house"]
            for m in NATURAL_MALEFICS if m in grahas
        )
        out[f"{nth}L benefic-joined"] = any(
            b != lord and grahas[b]["house"] == grahas[lord]["house"]
            for b in NATURAL_BENEFICS if b in grahas
        )
    return out


def discriminator_rows():
    """The charts pin_daridra proposed, replayed from cache. Free."""
    out = []
    for _split, _name, lat, lon, tz, when, chart in proposed_charts():
        path = cache_path("yoga", {
            "ayanamsa": 1, "coordinates": f"{lat},{lon}",
            "datetime": when.strftime("%Y-%m-%dT%H:%M:%S") + tz,
        })
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for group in payload["data"]["yoga_details"]:
            for item in group.get("yoga_list", []):
                if item["name"] == "Daridra Yoga":
                    out.append((chart, bool(item["has_yoga"])))
    return out


def main() -> int:
    charts = [(c, bool(t["Daridra Yoga"]))
              for _e, c, _v, t in load() if "Daridra Yoga" in t]
    extra = discriminator_rows()
    charts += extra
    print(f"{len(charts)} charts with a Daridra verdict "
          f"({len(extra)} of them discriminators)")
    rows = charts
    if len(rows) < 25:
        print("  run pin_daridra.py --verify first: too few to trust a fit")

    features = [wide_predicates(chart) for chart, _t in rows]
    keys = sorted(set().union(*(set(f) for f in features)))
    width = len(rows)
    full = (1 << width) - 1

    target = 0
    for index, (_chart, verdict) in enumerate(rows):
        if verdict:
            target |= 1 << index

    literals: list[tuple[str, int]] = []
    for key in keys:
        mask = 0
        for index, feature in enumerate(features):
            if feature.get(key, False):
                mask |= 1 << index
        if mask in (0, full):
            continue                      # constant across the set, no signal
        literals.append((key, mask))
        literals.append((f"NOT {key}", full ^ mask))
    print(f"{len(literals)} informative literals, "
          f"{bin(target).count('1')}/{width} charts positive")

    hits = []
    for name, mask in literals:
        if mask == target:
            hits.append(name)
    print(f"\n1-term fits: {len(hits)}  {hits[:6]}")

    two = []
    for (a, ma), (b, mb) in combinations(literals, 2):
        if ma | mb == target:
            two.append(f"{a} OR {b}")
        elif ma & mb == target:
            two.append(f"{a} AND {b}")
    print(f"2-term fits: {len(two)}  {two[:6]}")

    # Three terms, as (a OR b OR c) and (a AND b AND c) and the mixed shapes.
    three = []
    count = len(literals)
    for i in range(count):
        _a, ma = literals[i]
        if ma & ~target & full and ma | target != target:
            pass
        for j in range(i + 1, count):
            _b, mb = literals[j]
            or_ab, and_ab = ma | mb, ma & mb
            for k in range(j + 1, count):
                _c, mc = literals[k]
                if or_ab | mc == target:
                    three.append(f"{_a} OR {_b} OR {_c}")
                elif and_ab & mc == target:
                    three.append(f"{_a} AND {_b} AND {_c}")
                elif (or_ab & mc) == target:
                    three.append(f"({_a} OR {_b}) AND {_c}")
                elif (and_ab | mc) == target:
                    three.append(f"({_a} AND {_b}) OR {_c}")
                if len(three) > 40:
                    break
            if len(three) > 40:
                break
        if len(three) > 40:
            break
    print(f"3-term fits: {len(three)}")
    for formula in three[:20]:
        print(f"   {formula}")

    if not hits and not two and not three:
        print("\nNothing fits in one, two or three terms over "
              f"{len(literals) // 2} predicates and {width} charts.")
        print("That is a real result: Daridra is not a small boolean formula "
              "over placements and house lordships. Keep it flagged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
