"""Verify numerology against Prokerala's published OpenAPI examples.

Their spec ships a worked example for every numerology endpoint, including a
per-letter `name_chart`. Decoding those gives the name and date of birth they
used, which turns the whole spec into a free test fixture: no credits, no
network, no API key.

    python validation/against_prokerala_spec.py

The inputs were recovered rather than documented, so a mismatch can mean either
our formula is wrong OR that example used a different input. Anything flagged
here is a candidate for a paid probe, not a confirmed bug.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, ".")
from astro_engine import numerology as n  # noqa: E402

SPEC = Path("validation/spec/astrology.v2.yaml")

# Recovered from the name_chart in their examples: J=1 O=6 H=8 N=5 / D=4 O=6 E=5
# under the Pythagorean table is JOHN DOE. The datetime in their parameter
# documentation is 2004-02-12, which independently reproduces birth_month 2,
# birthday 3, life_path 11 and chaldean birth_number 3.
NAME = n.Name("John", "", "Doe")
BIRTH = date(2004, 2, 12)


def load_examples() -> dict[str, dict]:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    out = {}
    for path, node in spec["paths"].items():
        if not path.startswith("/numerology"):
            continue
        examples = (
            node.get("get", {}).get("responses", {}).get("200", {})
            .get("content", {}).get("application/json", {}).get("examples", {})
        )
        for wrapper in examples.values():
            out[path.replace("/numerology/", "")] = wrapper["value"]["data"]
    return out


def first_number(payload: dict):
    """Pull the headline `number` out of a response body."""
    for value in payload.values():
        if isinstance(value, dict) and "number" in value:
            return value["number"]
    return None


def main() -> int:
    if not SPEC.exists():
        print(f"spec not found at {SPEC}")
        print("curl -sSLO http://apiorigin.prokerala.com/spec/astrology.v2.yaml")
        return 1

    examples = load_examples()
    print("Verifying numerology against Prokerala's OpenAPI examples")
    print(f"Recovered inputs: {NAME.first} {NAME.last}, born {BIRTH}\n")

    checks: list[tuple[str, object, object]] = [
        ("life-path-number", n.life_path(BIRTH), first_number(examples["life-path-number"])),
        ("birthday-number", n.birthday_number(BIRTH), first_number(examples["birthday-number"])),
        ("birth-month-number", n.birth_month_number(BIRTH),
         first_number(examples["birth-month-number"])),
        ("expression-number", n.expression(NAME), first_number(examples["expression-number"])),
        ("destiny-number", n.destiny(NAME), first_number(examples["destiny-number"])),
        ("soul-urge-number", n.soul_urge(NAME), first_number(examples["soul-urge-number"])),
        ("personality-number", n.personality(NAME),
         first_number(examples["personality-number"])),
        ("inner-dream-number", n.inner_dream(NAME), first_number(examples["inner-dream-number"])),
        ("maturity-number", n.maturity(NAME, BIRTH), first_number(examples["maturity-number"])),
        ("attainment-number", n.attainment(NAME, BIRTH),
         first_number(examples["attainment-number"])),
        ("balance-number", n.balance(NAME), first_number(examples["balance-number"])),
        ("cornerstone-number", n.cornerstone(NAME), first_number(examples["cornerstone-number"])),
        ("capstone-number", n.capstone(NAME), first_number(examples["capstone-number"])),
        ("subconscious-self-number", n.subconscious_self(NAME),
         first_number(examples["subconscious-self-number"])),
        ("rational-thought-number", n.rational_thought(NAME, BIRTH),
         first_number(examples["rational-thought-number"])),
        ("chaldean/birth-number", n.chaldean_birth_number(BIRTH),
         first_number(examples["chaldean/birth-number"])),
        ("chaldean/daily-name-number", n.chaldean_daily_name(NAME),
         first_number(examples["chaldean/daily-name-number"])),
        ("chaldean/identity-initial-code-number", n.chaldean_identity_initial_code(NAME),
         first_number(examples["chaldean/identity-initial-code-number"])),
        # These two drop the year in Prokerala's implementation; confirmed live.
        ("chaldean/life-path-number [compat]",
         n.chaldean_life_path(BIRTH, prokerala_compatible=True),
         first_number(examples["chaldean/life-path-number"])),
        ("universal-year-number", n.universal_year(BIRTH.year),
         first_number(examples["universal-year-number"])),
        ("universal-month-number", n.universal_month(BIRTH.year, BIRTH.month),
         first_number(examples["universal-month-number"])),
        ("universal-day-number [compat]",
         n.universal_day(BIRTH.year, BIRTH.month, BIRTH.day, prokerala_compatible=True),
         first_number(examples["universal-day-number"])),
    ]

    # The letter tables themselves, straight from their name_chart.
    table_checks = []
    for endpoint, table in (("destiny-number", n.PYTHAGOREAN),
                            ("chaldean/daily-name-number", n.CHALDEAN)):
        chart = examples[endpoint].get("name_chart", {})
        for part, expected in chart.items():
            ours = n.letters(getattr(NAME, part.replace("_name", "")), table)
            for theirs, mine in zip(expected, ours):
                table_checks.append((
                    f"{endpoint} {theirs['character']}",
                    mine.number, theirs["number"],
                ))

    print(f"  {'check':42} {'engine':>8} {'spec':>8}")
    matched = mismatched = 0
    suspects = []
    for label, mine, theirs in table_checks + checks:
        ok = mine == theirs
        matched += ok
        mismatched += not ok
        if not ok:
            suspects.append(label)
        print(f"  {label:42} {str(mine):>8} {str(theirs):>8}  {'ok' if ok else 'DIFFERS'}")

    print(f"\n{matched} matched, {mismatched} differ")
    print()
    print("[compat] marks a value where Prokerala's own formula is wrong and we")
    print("reproduce it only in prokerala_compatible mode. Their Universal Day and")
    print("Chaldean Life Path both drop the year entirely; confirmed with live API")
    print("calls on 2004-02-12, 1990-01-15 and 2000-12-31.")
    if suspects:
        print("\nStill unexplained - candidates for a paid probe:")
        for label in suspects:
            print(f"  {label}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
