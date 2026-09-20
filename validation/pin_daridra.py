"""Identify Daridra Yoga by choosing charts that disagree, not by guessing.

Fitting formulas to the fifteen charts that carry a Daridra verdict is
hopeless: over 240 predicates, twenty-five different two-term formulas fit all
fifteen perfectly. That is not twenty-five discoveries, it is one dataset too
small to tell them apart, and any one of them shipped would be an overfit.

The way out is more signal rather than more search. Enumerate every one- and
two-term formula that fits what is already known, then look for birth moments
where the survivors disagree most sharply. One chart where the field splits in
half is worth more than a hundred where they all agree, and each answer from
the API roughly halves the candidate set.

    python validation/pin_daridra.py            # free: propose charts
    python validation/pin_daridra.py --verify   # paid: fetch and re-fit

Cost: 50 credits per proposed chart.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from itertools import combinations

sys.path.insert(0, ".")
from astro_engine.chart import BirthData, build  # noqa: E402
from astro_engine.constants import (  # noqa: E402
    NATURAL_BENEFICS, NATURAL_MALEFICS, SIGN_LORDS,
)
from validation.diagnose_yogas import load  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402

DUSTHANAS = {6, 8, 12}
KENDRAS = {1, 4, 7, 10}
TRIKONAS = {1, 5, 9}

PLACES = [
    ("Delhi", 28.6139, 77.2090, "+05:30"),
    ("Chennai", 13.0827, 80.2707, "+05:30"),
    ("London", 51.5074, -0.1278, "+00:00"),
    ("Sydney", -33.8688, 151.2093, "+10:00"),
]
ROUNDS = 24
CANDIDATE_LIMIT = 4000


def predicates(chart: dict) -> dict[str, bool]:
    """Everything a house-based yoga rule could plausibly be made of."""
    lagna = chart["lagna"]["sign_index"]
    grahas = chart["grahas"]
    out: dict[str, bool] = {}
    for nth in range(1, 13):
        lord = SIGN_LORDS[(lagna + nth - 1) % 12]
        house = grahas[lord]["house"]
        out[f"{nth}L dusthana"] = house in DUSTHANAS
        out[f"{nth}L kendra"] = house in KENDRAS
        out[f"{nth}L trikona"] = house in TRIKONAS
        out[f"{nth}L retro"] = bool(grahas[lord].get("is_retrograde"))
        out[f"{nth}L malefic"] = lord in NATURAL_MALEFICS
        for target in range(1, 13):
            out[f"{nth}L@{target}"] = house == target
    for house in range(1, 13):
        sign = (lagna + house - 1) % 12
        occupants = [p for p, v in grahas.items() if v["sign_index"] == sign]
        out[f"h{house} empty"] = not occupants
        out[f"h{house} malefic"] = any(p in NATURAL_MALEFICS for p in occupants)
        out[f"h{house} benefic"] = any(p in NATURAL_BENEFICS for p in occupants)
    return out


def formulas(keys: list[str]):
    """Every one- and two-term formula, as (name, evaluator)."""
    for key in keys:
        yield key, (lambda f, k=key: f[k])
        yield f"NOT {key}", (lambda f, k=key: not f[k])
    for left, right in combinations(keys, 2):
        yield f"{left} or {right}", (lambda f, a=left, b=right: f[a] or f[b])
        yield f"{left} and {right}", (lambda f, a=left, b=right: f[a] and f[b])


def survivors(observations):
    """Formulas consistent with every observation so far."""
    keys = sorted(observations[0][0])
    alive = []
    for name, rule in formulas(keys):
        if all(bool(rule(features)) == verdict
               for features, verdict in observations):
            alive.append((name, rule))
            if len(alive) > CANDIDATE_LIMIT:
                break
    return alive


def candidate_charts():
    """A spread of birth moments; the Lagna turns over roughly every two hours."""
    moment = datetime(1970, 2, 4, 0, 40)
    for step in range(ROUNDS * 9):
        place = PLACES[step % len(PLACES)]
        when = moment + timedelta(days=step * 53, hours=step * 3.1)
        yield place, when


def proposed_charts():
    """The charts this script proposes, deterministically.

    Same list every run, so once they are fetched the verdicts can be replayed
    from cache by anything else that wants them.
    """
    observations = []
    for _entry, chart, _view, theirs in load():
        if "Daridra Yoga" in theirs:
            observations.append((predicates(chart), bool(theirs["Daridra Yoga"])))
    alive = survivors(observations)

    scored = []
    for (name, lat, lon, tz), when in candidate_charts():
        chart = build(
            BirthData(when.year, when.month, when.day, when.hour, when.minute, 0,
                      lat, lon),
            vargas=["D1"], dasha_depth=1,
        )
        features = predicates(chart)
        yes = sum(1 for _, rule in alive if rule(features))
        scored.append((min(yes, len(alive) - yes), name, lat, lon, tz, when, chart))
    scored.sort(key=lambda row: -row[0])
    return scored[:ROUNDS]


def main(verify: bool) -> int:
    observations = []
    for entry, chart, _view, theirs in load():
        if "Daridra Yoga" in theirs:
            observations.append((predicates(chart), bool(theirs["Daridra Yoga"])))
    print(f"{len(observations)} charts already known")

    alive = survivors(observations)
    print(f"{len(alive)} formulas fit all of them\n")
    if len(alive) <= 1:
        print("already identified:", alive[0][0] if alive else "nothing fits")
        return 0

    # Score each proposed chart by how evenly it splits the survivors.
    scored = []
    for (name, lat, lon, tz), when in candidate_charts():
        chart = build(
            BirthData(when.year, when.month, when.day, when.hour, when.minute, 0,
                      lat, lon),
            vargas=["D1"], dasha_depth=1,
        )
        features = predicates(chart)
        yes = sum(1 for _, rule in alive if rule(features))
        split = min(yes, len(alive) - yes)
        scored.append((split, name, lat, lon, tz, when, features))
    scored.sort(key=lambda row: -row[0])

    chosen = scored[:ROUNDS]
    print(f"proposing {len(chosen)} charts; best splits "
          f"{[row[0] for row in chosen[:6]]} of {len(alive)}")
    if not verify:
        print("\nrun again with --verify to fetch them (50 credits each)")
        return 0

    answers = run([
        ("yoga", {"ayanamsa": 1, "coordinates": f"{lat},{lon}",
                  "datetime": when.strftime("%Y-%m-%dT%H:%M:%S") + tz})
        for _, name, lat, lon, tz, when, _ in chosen
    ], "daridra discriminators")

    added = 0
    for (_, name, lat, lon, tz, when, features), answer in zip(chosen, answers):
        if isinstance(answer, Exception):
            continue
        verdict = None
        for group in answer["data"]["yoga_details"]:
            for item in group.get("yoga_list", []):
                if item["name"] == "Daridra Yoga":
                    verdict = bool(item["has_yoga"])
        if verdict is None:
            continue
        observations.append((features, verdict))
        added += 1
        print(f"   {when:%Y-%m-%d %H:%M} {name:8} Daridra={verdict}")

    print(f"\n{added} new charts, {len(observations)} total")
    alive = survivors(observations)
    print(f"{len(alive)} formulas still fit")
    for formula, _ in alive[:15]:
        print(f"   {formula}")
    if len(alive) == 1:
        print("\nIDENTIFIED. Put this in yogas.daridra and drop it from UNVERIFIED.")
    elif not alive:
        print("\nNothing fits any more: the rule is not a one- or two-term "
              "house formula. That is a real result -- record it rather than "
              "widening the search until something sticks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--verify" in sys.argv))
