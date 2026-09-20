"""Porutham parity, by sweeping one nakshatra against all twenty-seven.

The thirumana endpoint takes nakshatra indices directly -- no coordinates, no
birth time -- so the rule space can be explored systematically instead of
through whatever nakshatras a chart happens to produce. Each sweep fixes the
bride's star and walks the groom's across all 27, which is exactly what is
needed to see a count-based rule's shape.

    python validation/verify_porutham.py

Cost: 50 credits per pair. Two sweeps is 2,700.
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")
from astro_engine import porutham  # noqa: E402
from astro_engine.constants import NAKSHATRAS  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

# Prokerala numbers nakshatras from zero here, matching our own indices.
ID_OFFSET = 0

# (girl nakshatra, girl pada, boy pada). Two brides far apart in the cycle, so
# a rule that happens to fit one will not fit the other by accident.
SWEEPS = [(0, 1, 1), (13, 2, 3)]


def main() -> int:
    checks = 0
    failures: list[str] = []
    shape: dict[str, list[str]] = {}

    for girl, girl_pada, boy_pada in SWEEPS:
        for boy in range(27):
            mine = porutham.compute(boy, boy_pada, girl, girl_pada, twelve=True)
            theirs = fetch("thirumana-porutham", {
                "girl_nakshatra": girl + ID_OFFSET,
                "girl_nakshatra_pada": girl_pada,
                "boy_nakshatra": boy + ID_OFFSET,
                "boy_nakshatra_pada": boy_pada,
            })["data"]

            for ours, other in zip(mine["matches"], theirs["matches"]):
                if ours["parity"] != "verified":
                    continue
                checks += 1
                if ours["name"] != other["name"]:
                    failures.append(
                        f"name {ours['name']} vs {other['name']}")
                    continue
                if ours["has_porutham"] != other["has_porutham"]:
                    failures.append(
                        f"{NAKSHATRAS[girl]}/{NAKSHATRAS[boy]} {other['name']}: "
                        f"{ours['has_porutham']} vs {other['has_porutham']}"
                    )
                    shape.setdefault(other["name"], []).append(
                        f"{porutham.count_from(girl, boy)}"
                    )
            # The total mixes verified and unverified checks, so it is not
            # something this engine claims to reproduce yet.

    print(f"{checks - len(failures)}/{checks} porutham checks pass "
          f"(all twelve rules)")
    for name, counts in sorted(shape.items()):
        print(f"  {name}: disagrees at counts {sorted(set(counts), key=int)}")
    for line in failures[:20]:
        print(f"    {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
