"""Write the measured star tables into astro_engine/porutham.py.

`sweep_porutham_stars.py` measures Rasi, Rasi Lord, Vashya and Varna over the
whole 27x27 star space at pada 1. What can be done with that result differs
per check, and the difference is the whole point:

*Rasi and Rasi Lord are pada-insensitive.* Across every star pair observed at
more than one pada, neither ever changed its answer. For them the 27x27 table
is the complete function and they can be marked verified.

*Vashya and Varna are not.* A bride in Bharani and a groom in Punarvasu answer
differently at pada 1 and pada 3, and their signs do not move between those
padas, so the sign cannot be what changed. Their real input space is the pada
pair, 108x108, and no modulus tried collapses it. The pada-1 table is still
far better than the formula it replaces -- exact where the formula scored 165
of 506 -- so it ships, but flagged, and only Varna keeps a rule because its
modulo-nine rank is exact on the whole pada-1 table.

    python validation/install_porutham_tables.py

Costs nothing: it only reads the JSON the sweep wrote.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, ".")

TABLES = pathlib.Path("validation/porutham_star_tables.json")
MODULE = pathlib.Path("astro_engine/porutham.py")

CONSTANT_NAMES = {
    "Rasi Porutham": "RASI_TABLE",
    "Rasi Lord Porutham": "RASI_LORD_TABLE",
    "Vashya Porutham": "VASHYA_TABLE",
}

BLOCK_START = "# --- measured star tables "
MARKER = BLOCK_START + "-" * (79 - len(BLOCK_START))


def render(name: str, grid: list[list[int]]) -> str:
    rows = ",\n".join(
        f'    "{"".join(str(cell) for cell in row)}"' for row in grid
    )
    return f"{name} = (\n{rows},\n)\n"


def main() -> int:
    if not TABLES.exists():
        print(f"{TABLES} not found -- run sweep_porutham_stars.py first")
        return 1
    data = json.loads(TABLES.read_text(encoding="utf-8"))

    missing = [rule for rule in CONSTANT_NAMES if rule not in data]
    if missing:
        print(f"the sweep did not finish these: {missing}")
        return 1
    for rule in CONSTANT_NAMES:
        grid = data[rule]
        if len(grid) != 27 or any(len(row) != 27 for row in grid):
            print(f"{rule}: table is not 27x27")
            return 1
        if any(cell not in (0, 1) for row in grid for cell in row):
            print(f"{rule}: table still has unmeasured cells")
            return 1

    body = [
        MARKER,
        "",
        "# Rasi, Rasi Lord and Vashya are not the sign rules they look like:",
        "# hold the sign fixed, move the nakshatra underneath it, and the",
        "# answer changes. As functions of the star pair they are consistent,",
        "# and since the whole input space is then 729 pairs, all 729 were",
        "# fetched. These are measurements, not fits -- rows are the bride's",
        "# nakshatra, columns the groom's, '1' means the check passes.",
        "#",
        "# Rasi and Rasi Lord never changed answer across padas, so for them",
        "# this is the entire function. Vashya does change, so its table is",
        "# exact at pada 1 and an approximation elsewhere; it stays flagged.",
        "",
    ]
    for rule, name in CONSTANT_NAMES.items():
        body.append(render(name, data[rule]))
    body += [
        "for _table in (RASI_TABLE, RASI_LORD_TABLE, VASHYA_TABLE):",
        "    assert len(_table) == NAKSHATRA_COUNT",
        "    assert all(len(_row) == NAKSHATRA_COUNT for _row in _table)",
        '    assert all(_cell in "01" for _row in _table for _cell in _row)',
        "",
        "",
        "def _measured(table: tuple[str, ...], boy: int, girl: int) -> bool:",
        '    return table[girl % NAKSHATRA_COUNT][boy % NAKSHATRA_COUNT] == "1"',
        "",
    ]
    block = "\n".join(body)

    source = MODULE.read_text(encoding="utf-8")
    anchor = "\n# --- 8 rasi "
    if MARKER in source:
        head, _, tail = source.partition(MARKER)
        source = head + block + tail[tail.index(anchor):]
    else:
        source = source.replace(anchor, "\n" + block + anchor, 1)
    MODULE.write_text(source, encoding="utf-8")
    print(f"installed 3 tables of 27x27 into {MODULE}")
    print("Rasi and Rasi Lord are now complete; Vashya is pada-1 only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
