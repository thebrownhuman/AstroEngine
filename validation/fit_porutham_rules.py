"""Read the porutham rules out of every cached thirumana response at once.

Pulls together the three sweeps -- the original star sweeps, the twelve-by-
twelve sign grid, and the factorial arms -- normalises them, and reports what
each rule actually depends on.

Two corrections are applied while reading:

*Pada four is Prokerala's own off-by-one.* Sending pada 4 makes every
nakshatra-based check behave as though the groom were in the first pada of the
*next* nakshatra. Pada 0 is rejected outright, so this is not a zero-based
convention -- it is a bug, and the fourth pada of the twenty-seventh nakshatra
wraps to Ashwini. The rasi-based checks are unaffected, because pada 4 of one
star and pada 1 of the next cover the same three degrees twenty of the zodiac.

*The four "rasi" checks are not rasi checks.* Holding the sign fixed and
moving the nakshatra underneath it changes their answer, so Rasi, Rasi Lord,
Vashya and Varna are functions of the star pair like the other eight. The
twelve-by-twelve grid this script still prints is therefore a summary, not a
rule: read the conflict counts above it before trusting a cell.

Costs nothing: it only reads validation/.cache.
"""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import NAKSHATRAS, SIGNS_EN  # noqa: E402
from validation.parallel_fetch import cache_path  # noqa: E402
from validation.verify_porutham_signs import FIRST, MIDDLE  # noqa: E402
from validation.diagnose_porutham_factors import ARMS  # noqa: E402
from validation.verify_porutham import SWEEPS  # noqa: E402

import json  # noqa: E402

PADAS_PER_NAKSHATRA = 4


def effective_star(nakshatra: int, pada: int) -> int:
    """What Prokerala's star rules actually use for this (nakshatra, pada)."""
    if pada == PADAS_PER_NAKSHATRA:
        return (nakshatra + 1) % 27
    return nakshatra


def every_pair() -> list[tuple[tuple[int, int], tuple[int, int], dict]]:
    """(girl, boy, verdicts) for every thirumana response on disk."""
    wanted = []
    for girl, girl_pada, boy_pada in SWEEPS:
        wanted += [((girl, girl_pada), (boy, boy_pada)) for boy in range(27)]
    wanted += [(g, b) for g in MIDDLE for b in MIDDLE]
    wanted += [(MIDDLE[0], b) for b in FIRST]
    for girl, boy_pada in ARMS.values():
        wanted += [(girl, (boy, boy_pada)) for boy in range(27)]

    out, seen = [], set()
    for girl, boy in wanted:
        if (girl, boy) in seen:
            continue
        seen.add((girl, boy))
        path = cache_path("thirumana-porutham", {
            "girl_nakshatra": girl[0], "girl_nakshatra_pada": girl[1],
            "boy_nakshatra": boy[0], "boy_nakshatra_pada": boy[1],
        })
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "ok":
            continue
        out.append((girl, boy, {m["name"]: m["has_porutham"]
                                for m in payload["data"]["matches"]}))
    return out


def stars(girl, boy):
    return effective_star(*girl), effective_star(*boy)


def signs(girl, boy):
    return P.rasi_of(*girl), P.rasi_of(*boy)


def report(rows, rule, key, label):
    table = defaultdict(set)
    for girl, boy, verdicts in rows:
        if rule in verdicts:
            table[key(girl, boy)].add(verdicts[rule])
    conflicts = {k: v for k, v in table.items() if len(v) > 1}
    print(f"   {label}: {len(table)} distinct values, "
          f"{'CONSISTENT' if not conflicts else f'{len(conflicts)} conflicts'}")
    return table, conflicts


def main() -> int:
    rows = every_pair()
    print(f"{len(rows)} cached pairs\n")

    for rule in ("Dina Porutham", "Gana Porutham", "Mahendra Porutham",
                 "Stree Deergha Porutham", "Yoni Porutham", "Veda Porutham",
                 "Rajju Porutham", "Nadi Porutham"):
        print(rule)
        report(rows, rule, lambda g, b: P.count_from(*stars(g, b)), "count")
        report(rows, rule, lambda g, b: stars(g, b), "star pair")

        # How often does the engine get it right once pada 4 is accounted for?
        wrong = 0
        total = 0
        examples = []
        for girl, boy, verdicts in rows:
            if rule not in verdicts:
                continue
            gs, bs = stars(girl, boy)
            mine = P.compute(bs, 1, gs, 1, twelve=True)
            value = next(e["has_porutham"] for e in mine["matches"]
                         if e["name"] == rule)
            total += 1
            if value != verdicts[rule]:
                wrong += 1
                if len(examples) < 3:
                    examples.append(f"{NAKSHATRAS[gs]}/{NAKSHATRAS[bs]}")
        flag = "OK" if not wrong else f"{wrong} WRONG  e.g. {', '.join(examples)}"
        print(f"   engine: {total - wrong}/{total}  {flag}\n")

    for rule in ("Rasi Porutham", "Rasi Lord Porutham", "Vashya Porutham",
                 "Varna Porutham"):
        print(rule)
        table, conflicts = report(rows, rule, signs, "sign pair")
        wrong = sum(1 for girl, boy, v in rows if rule in v
                    and next(e["has_porutham"] for e in
                             P.compute(boy[0], boy[1], girl[0], girl[1],
                                       twelve=True)["matches"]
                             if e["name"] == rule) != v[rule])
        print(f"   engine wrong on {wrong} pairs; "
              f"{len(table)}/144 sign cells observed\n")

    # The grids, ready to paste.
    for rule, name in (("Rasi Porutham", "RASI"),
                       ("Rasi Lord Porutham", "RASI_LORD"),
                       ("Vashya Porutham", "VASHYA"),
                       ("Varna Porutham", "VARNA")):
        table, _ = report(rows, rule, signs, "sign pair")
        print(f"\n{name}_PORUTHAM_GRID = (")
        for girl_sign in range(12):
            cells = []
            for boy_sign in range(12):
                value = table.get((girl_sign, boy_sign))
                cells.append("?" if not value else str(int(next(iter(value)))))
            print(f'    "{"".join(cells)}",  # {SIGNS_EN[girl_sign]}')
        print(")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
