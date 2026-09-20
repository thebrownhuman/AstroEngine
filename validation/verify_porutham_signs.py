"""Recover the six rasi-based poruthams by sweeping sign pairs.

The star sweeps in `verify_porutham.py` pinned the six count-based rules and
left six that turn on the rasi pair. A star sweep cannot separate those: it
walks twenty-seven nakshatras through only twelve signs, several at a time.

So sweep the signs instead. Nine padas make a sign, so one (nakshatra, pada)
pair per sign gives twelve representatives, and every ordered pair of those is
a twelve-by-twelve grid -- exactly the shape the disagreements implied.

A second pass holds the bride fixed and moves the groom to the *first* pada of
each sign rather than the middle one. Same signs, different degrees within
them, so if Vashya really splits some signs in half it shows up here and
nowhere else.

    python validation/verify_porutham_signs.py

Cost: 50 credits per pair, 168 pairs, 8,400 credits. Runs across every live
app at once, so about ten minutes rather than forty.
"""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import SIGNS_EN  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402

RASI_RULES = ("Rasi Porutham", "Rasi Lord Porutham", "Vashya Porutham",
              "Varna Porutham")
STAR_RULES = ("Rajju Porutham", "Nadi Porutham")

# Middle pada of each sign, and the first, so the pair differs in degree but
# not in sign.
MIDDLE = [( (9 * r + 4) // 4, (9 * r + 4) % 4 + 1 ) for r in range(12)]
FIRST = [( (9 * r) // 4, (9 * r) % 4 + 1 ) for r in range(12)]

# One bride for the degree probe. Mesha, where the earlier sweep disagreed.
PROBE_GIRL = MIDDLE[0]


def job(girl: tuple[int, int], boy: tuple[int, int]) -> tuple[str, dict]:
    return ("thirumana-porutham", {
        "girl_nakshatra": girl[0], "girl_nakshatra_pada": girl[1],
        "boy_nakshatra": boy[0], "boy_nakshatra_pada": boy[1],
    })


def verdicts(payload: dict) -> dict[str, bool]:
    return {m["name"]: m["has_porutham"] for m in payload["data"]["matches"]}


def main() -> int:
    grid_pairs = [(g, b) for g in MIDDLE for b in MIDDLE]
    probe_pairs = [(PROBE_GIRL, b) for b in FIRST]
    pairs = grid_pairs + probe_pairs

    answers = run([job(g, b) for g, b in pairs], "porutham signs")

    truth: dict[str, dict[tuple[int, int], bool]] = defaultdict(dict)
    failed = 0
    for (girl, boy), answer in zip(pairs, answers):
        if isinstance(answer, Exception):
            failed += 1
            continue
        girl_sign = P.rasi_of(*girl)
        boy_sign = P.rasi_of(*boy)
        for name, value in verdicts(answer).items():
            truth[name][(girl_sign, boy_sign)] = value

    if failed:
        print(f"note: {failed} pairs failed and are excluded")

    # What the engine says now, against what came back.
    print()
    mismatch: dict[str, list[str]] = defaultdict(list)
    checks = 0
    for (girl, boy), answer in zip(pairs, answers):
        if isinstance(answer, Exception):
            continue
        mine = P.compute(boy[0], boy[1], girl[0], girl[1], twelve=True)
        theirs = verdicts(answer)
        for entry in mine["matches"]:
            checks += 1
            if entry["has_porutham"] != theirs[entry["name"]]:
                mismatch[entry["name"]].append(
                    f"{SIGNS_EN[P.rasi_of(*girl)]}/{SIGNS_EN[P.rasi_of(*boy)]}")

    print(f"{checks - sum(len(v) for v in mismatch.values())}/{checks} "
          f"checks agree before any correction")
    for name in sorted(mismatch):
        print(f"  {name}: {len(mismatch[name])} disagreements")

    # The degree probe: same signs, different padas.
    print()
    degree_sensitive = []
    for boy_middle, boy_first, middle_answer, probe_answer in zip(
        MIDDLE, FIRST,
        [a for (g, _), a in zip(pairs, answers) if g == PROBE_GIRL][:12],
        answers[len(grid_pairs):],
    ):
        if isinstance(middle_answer, Exception) or isinstance(probe_answer, Exception):
            continue
        if P.rasi_of(*boy_middle) != P.rasi_of(*boy_first):
            continue
        a, b = verdicts(middle_answer), verdicts(probe_answer)
        for name in RASI_RULES:
            if a[name] != b[name]:
                degree_sensitive.append(
                    f"{name} in {SIGNS_EN[P.rasi_of(*boy_first)]}")
    if degree_sensitive:
        print("degree matters inside a sign for: "
              + ", ".join(sorted(set(degree_sensitive))))
    else:
        print("no rasi rule changed with the pada inside a sign: "
              "all six are functions of the sign pair alone")

    # Print each grid as a literal ready to paste in.
    for name in RASI_RULES + STAR_RULES:
        grid = truth.get(name)
        if not grid:
            continue
        print(f"\n# {name}: rows are the bride's sign, columns the groom's")
        print(f"{name.split()[0].upper()}_GRID = [")
        for girl_sign in range(12):
            row = [int(grid.get((girl_sign, boy_sign), -1)) for boy_sign in range(12)]
            print(f"    {row},  # {SIGNS_EN[girl_sign]}")
        print("]")

    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
