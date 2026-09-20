"""Measure the last four poruthams over every star pair there is.

Rasi, Rasi Lord, Vashya and Varna resisted every rule tried. They look like
sign rules and are not: hold the sign fixed and move the nakshatra underneath
it and the answer changes. As functions of the star pair they are perfectly
consistent, so the honest thing is to stop guessing at a formula and measure
the whole table -- twenty-seven brides by twenty-seven grooms, 729 cells.

That is the complete input space. These four checks take nothing but the two
nakshatras, so a full table is not a sample of the rule, it *is* the rule.

Pada 1 throughout: pada 4 is Prokerala's off-by-one, and padas 1 to 3 give the
same answer for every star-based check, which the factorial arms established.

    python validation/sweep_porutham_stars.py

Cost: 50 credits per uncached pair, up to 36,450 for a cold run. Every pair
already on disk from an earlier sweep is reused.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import NAKSHATRAS  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402
from validation.verify_porutham_signs import job, verdicts  # noqa: E402

PADA = 1
NAKSHATRA_COUNT = 27
TARGET_RULES = ("Rasi Porutham", "Rasi Lord Porutham",
                "Vashya Porutham", "Varna Porutham")
ALL_RULES = TARGET_RULES + (
    "Dina Porutham", "Gana Porutham", "Mahendra Porutham",
    "Stree Deergha Porutham", "Yoni Porutham", "Veda Porutham",
    "Rajju Porutham", "Nadi Porutham",
)
OUTPUT = "validation/porutham_star_tables.json"


def main() -> int:
    pairs = [(girl, boy)
             for girl in range(NAKSHATRA_COUNT)
             for boy in range(NAKSHATRA_COUNT)]
    answers = run([job((g, PADA), (b, PADA)) for g, b in pairs],
                  "porutham star table")

    tables: dict[str, list[list[int]]] = {
        rule: [[-1] * NAKSHATRA_COUNT for _ in range(NAKSHATRA_COUNT)]
        for rule in ALL_RULES
    }
    missing = []
    for (girl, boy), answer in zip(pairs, answers):
        if isinstance(answer, Exception):
            missing.append((girl, boy))
            continue
        values = verdicts(answer)
        for rule in ALL_RULES:
            tables[rule][girl][boy] = int(values[rule])

    collected = NAKSHATRA_COUNT ** 2 - len(missing)
    print(f"\n{collected}/{NAKSHATRA_COUNT ** 2} cells measured")
    if missing:
        print(f"  {len(missing)} missing, e.g. "
              f"{[(NAKSHATRAS[g], NAKSHATRAS[b]) for g, b in missing[:3]]}")

    # How well does the engine do on each rule over the whole space?
    print()
    for rule in ALL_RULES:
        wrong = 0
        total = 0
        for girl in range(NAKSHATRA_COUNT):
            for boy in range(NAKSHATRA_COUNT):
                theirs = tables[rule][girl][boy]
                if theirs < 0:
                    continue
                total += 1
                mine = next(e["has_porutham"] for e in
                            P.compute(boy, PADA, girl, PADA,
                                      twelve=True)["matches"]
                            if e["name"] == rule)
                if int(mine) != theirs:
                    wrong += 1
        mark = "ok" if not wrong else f"{wrong} wrong"
        print(f"   {rule:26} {total - wrong}/{total}  {mark}")

    if not missing:
        with open(OUTPUT, "w", encoding="utf-8") as handle:
            json.dump({rule: tables[rule] for rule in TARGET_RULES},
                      handle, separators=(",", ":"))
        print(f"\nwrote {OUTPUT}")

    # A sanity read on the shape of each measured table.
    print()
    for rule in TARGET_RULES:
        grid = tables[rule]
        rows = defaultdict(list)
        for girl in range(NAKSHATRA_COUNT):
            rows[tuple(grid[girl])].append(girl)
        symmetric = all(grid[a][b] == grid[b][a]
                        for a in range(NAKSHATRA_COUNT)
                        for b in range(NAKSHATRA_COUNT)
                        if grid[a][b] >= 0 and grid[b][a] >= 0)
        print(f"   {rule:26} {len(rows):2} distinct bride rows, "
              f"{'symmetric' if symmetric else 'not symmetric'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
