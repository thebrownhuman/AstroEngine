"""Separate nakshatra from pada from rasi in the porutham rules.

The sign sweep in `verify_porutham_signs.py` walks one (nakshatra, pada) pair
per sign, which means nakshatra, pada and rasi all move together. Any rule
that looked broken there might really be broken, or might just be the design
failing to tell three variables apart. Mahendra, for instance, came back true
exactly when the two representatives shared a pada -- which is either a real
finding or a coincidence of the twelve chosen pairs.

So vary one thing at a time:

    A  one bride, all 27 grooms, groom pada 1
    B  the same bride, all 27 grooms, groom pada 3
    C  a second bride at a different pada, all 27 grooms, groom pada 1

A against B isolates the groom's pada: if the star rules are identical the
pada is irrelevant and the sign sweep's disagreements come from elsewhere.
A against C isolates the bride.

    python validation/diagnose_porutham_factors.py

Cost: 81 pairs, 4,050 credits.
"""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import NAKSHATRAS  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402
from validation.verify_porutham_signs import job, verdicts  # noqa: E402

STAR_RULES = ("Dina Porutham", "Gana Porutham", "Mahendra Porutham",
              "Stree Deergha Porutham", "Yoni Porutham", "Veda Porutham",
              "Rajju Porutham", "Nadi Porutham")
RASI_RULES = ("Rasi Porutham", "Rasi Lord Porutham", "Vashya Porutham",
              "Varna Porutham")

ARMS = {
    "A": ((1, 1), 1),
    "B": ((1, 1), 3),
    "C": ((5, 2), 1),
}


def collect() -> dict[str, dict[int, dict[str, bool]]]:
    jobs, index = [], []
    for arm, (girl, boy_pada) in ARMS.items():
        for boy in range(27):
            jobs.append(job(girl, (boy, boy_pada)))
            index.append((arm, boy))

    answers = run(jobs, "porutham factors")
    out: dict[str, dict[int, dict[str, bool]]] = defaultdict(dict)
    for (arm, boy), answer in zip(index, answers):
        if isinstance(answer, Exception):
            continue
        out[arm][boy] = verdicts(answer)
    return out


def compare(left: dict, right: dict, label: str) -> None:
    shared = sorted(set(left) & set(right))
    differing = defaultdict(list)
    for boy in shared:
        for rule in STAR_RULES + RASI_RULES:
            if left[boy][rule] != right[boy][rule]:
                differing[rule].append(NAKSHATRAS[boy])
    print(f"\n{label}  ({len(shared)} grooms compared)")
    if not differing:
        print("   identical on every rule")
        return
    for rule in sorted(differing):
        names = differing[rule]
        print(f"   {rule}: differs for {len(names)} grooms "
              f"(e.g. {', '.join(names[:4])})")


def check_engine(arm: str, data: dict[int, dict[str, bool]]) -> None:
    girl, boy_pada = ARMS[arm]
    wrong = defaultdict(list)
    total = 0
    for boy, theirs in sorted(data.items()):
        mine = P.compute(boy, boy_pada, girl[0], girl[1], twelve=True)
        for entry in mine["matches"]:
            total += 1
            if entry["has_porutham"] != theirs[entry["name"]]:
                wrong[entry["name"]].append(NAKSHATRAS[boy])
    passed = total - sum(len(v) for v in wrong.values())
    print(f"\narm {arm}  bride {NAKSHATRAS[girl[0]]} pada {girl[1]}, "
          f"grooms at pada {boy_pada}: {passed}/{total} agree")
    for rule in sorted(wrong):
        names = wrong[rule]
        print(f"   {rule}: {len(names)} wrong -- {', '.join(names[:6])}")
        if "Dina" in rule or "Mahendra" in rule or "Stree" in rule:
            counts = sorted(P.count_from(girl[0], NAKSHATRAS.index(n))
                            for n in names)
            print(f"      at counts {counts}")


def main() -> int:
    data = collect()
    for arm in ARMS:
        if arm in data:
            check_engine(arm, data[arm])

    if "A" in data and "B" in data:
        compare(data["A"], data["B"], "A vs B: only the groom's pada changed")
    if "A" in data and "C" in data:
        compare(data["A"], data["C"], "A vs C: only the bride changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
