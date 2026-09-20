"""Map Prokerala's rajju groups.

Rajju is the one porutham whose group table the sweeps so far cannot pin down.
What they do show is its shape: the check only ever fails when the groom's
star counted from the bride's lands on 1, 7, 10, 13, 16, 19, 22 or 25 -- every
count one more than a multiple of three -- and inside that set it depends on
which stars they are.

Two cheap designs settle it:

*The diagonal.* Pairing a star with itself fails for Bharani but passes for
Ashwini, so a star's own rajju is not always able to clash. Twenty-seven calls
say which stars carry a clashing rajju at all.

*Two full rows.* A bride swept against all twenty-seven grooms gives that
bride's whole group in one pass. Ashwini, Bharani, Ardra and Chitra already
have rows; Rohini and Purva Phalguni are added because they are the two
brides whose partial rows hint at groups nothing else covers.

    python validation/sweep_rajju.py

Cost: 81 pairs, 4,050 credits, minus whatever is already cached.
"""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import NAKSHATRAS  # noqa: E402
from validation.fit_porutham_rules import every_pair  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402
from validation.verify_porutham_signs import job, verdicts  # noqa: E402

RULE = "Rajju Porutham"
# Padas one and three only: pada four is Prokerala's off-by-one, and one pada
# from each half of a star is enough since rajju does not look at the sign.
PADA = 1
EXTRA_ROWS = (3, 10)


def main() -> int:
    pairs = [((n, PADA), (n, PADA)) for n in range(27)]
    for girl in EXTRA_ROWS:
        pairs += [((girl, PADA), (boy, PADA)) for boy in range(27)]

    seen = set()
    unique = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)

    answers = run([job(g, b) for g, b in unique], "rajju")

    rows: dict[int, dict[int, bool]] = defaultdict(dict)
    for (girl, boy), answer in zip(unique, answers):
        if isinstance(answer, Exception):
            continue
        rows[girl[0]][boy[0]] = verdicts(answer)[RULE]

    # Fold in everything already on disk.
    for girl, boy, values in every_pair():
        if girl[1] != 4 and boy[1] != 4 and RULE in values:
            rows[girl[0]].setdefault(boy[0], values[RULE])

    print("\nstars that clash with themselves:")
    self_clash = sorted(n for n in range(27) if rows.get(n, {}).get(n) is False)
    free = sorted(n for n in range(27) if rows.get(n, {}).get(n) is True)
    print(f"   clash: {self_clash}")
    print(f"   free : {free}")

    print("\nfull rows:")
    groups = {}
    for girl in sorted(rows):
        row = rows[girl]
        if len(row) < 27:
            continue
        same = sorted(b for b, ok in row.items() if not ok)
        groups[girl] = same
        print(f"   {NAKSHATRAS[girl]:18} ({girl:2}) -> {same}")

    # Anything consistent? A group must contain its own members' groups.
    print("\nconsistency of the groups found:")
    for girl, members in groups.items():
        for other in members:
            if other in groups and sorted(groups[other]) != sorted(members):
                print(f"   {NAKSHATRAS[girl]} and {NAKSHATRAS[other]} "
                      f"disagree: {members} vs {groups[other]}")
                break
        else:
            print(f"   {NAKSHATRAS[girl]:18} consistent")

    print("\nengine now:")
    total = wrong = 0
    for girl, row in rows.items():
        for boy, value in row.items():
            total += 1
            if P.rajju(boy, girl) != value:
                wrong += 1
    print(f"   {total - wrong}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
