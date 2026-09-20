"""Read the porutham rules back out of the cached sweep responses.

Each sweep holds the bride's star fixed and walks the groom's across all
twenty-seven, so for a count-based rule the answer is simply the set of counts
that came back true. For a table-based rule it is the set of categories. This
prints both views for every porutham, which is enough to write the rule down.

Costs nothing: it only reads validation/.cache.
"""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import matching as M  # noqa: E402
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import SIGN_LORDS  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402
from validation.verify_porutham import SWEEPS  # noqa: E402


def truth() -> dict[str, list[tuple]]:
    """(girl, girl_pada, boy, boy_pada, verdict) per porutham name."""
    out: dict[str, list[tuple]] = defaultdict(list)
    for girl, girl_pada, boy_pada in SWEEPS:
        for boy in range(27):
            data = fetch("thirumana-porutham", {
                "girl_nakshatra": girl, "girl_nakshatra_pada": girl_pada,
                "boy_nakshatra": boy, "boy_nakshatra_pada": boy_pada,
            })["data"]
            for entry in data["matches"]:
                out[entry["name"]].append(
                    (girl, girl_pada, boy, boy_pada, entry["has_porutham"])
                )
    return out


def main() -> int:
    table = truth()

    for name, rows in table.items():
        print(f"\n=== {name}")
        by_count = defaultdict(set)
        for girl, _, boy, _, verdict in rows:
            by_count[P.count_from(girl, boy)].add(verdict)
        consistent = all(len(v) == 1 for v in by_count.values())
        good = sorted(c for c, v in by_count.items() if v == {True})
        print(f"  count-consistent: {consistent}; true at counts {good}")

        # Category views, whichever is relevant.
        for label, key in (
            ("gana", lambda g, gp, b, bp: (M.GANA_BY_NAKSHATRA[b],
                                           M.GANA_BY_NAKSHATRA[g])),
            ("nadi", lambda g, gp, b, bp: (M.NADI_BY_NAKSHATRA[b],
                                           M.NADI_BY_NAKSHATRA[g])),
            ("rajju", lambda g, gp, b, bp: (P.RAJJU_BY_NAKSHATRA[b],
                                            P.RAJJU_BY_NAKSHATRA[g])),
            ("yoni", lambda g, gp, b, bp: (M.YONI_BY_NAKSHATRA[b][0],
                                           M.YONI_BY_NAKSHATRA[g][0])),
            ("rasi gap", lambda g, gp, b, bp: (
                (P.rasi_of(b, bp) - P.rasi_of(g, gp)) % 12 + 1,)),
            ("lords", lambda g, gp, b, bp: (SIGN_LORDS[P.rasi_of(b, bp)],
                                            SIGN_LORDS[P.rasi_of(g, gp)])),
            ("vasya", lambda g, gp, b, bp: (
                M.vasya_group(P.rasi_of(b, bp), P.degree_of(b, bp)),
                M.vasya_group(P.rasi_of(g, gp), P.degree_of(g, gp)))),
            ("varna", lambda g, gp, b, bp: (
                M.VARNA_BY_SIGN[P.rasi_of(b, bp)],
                M.VARNA_BY_SIGN[P.rasi_of(g, gp)])),
        ):
            buckets = defaultdict(set)
            for girl, girl_pada, boy, boy_pada, verdict in rows:
                buckets[key(girl, girl_pada, boy, boy_pada)].add(verdict)
            if all(len(v) == 1 for v in buckets.values()) and len(buckets) > 1:
                yes = sorted(k for k, v in buckets.items() if v == {True})
                no = sorted(k for k, v in buckets.items() if v == {False})
                print(f"  {label}-consistent: true {yes}")
                print(f"  {' ' * len(label)}  false {no}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
