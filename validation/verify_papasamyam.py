"""Recover the papasamyam point weights.

The grid -- which of Mars, Saturn, Sun and Rahu sits in a papa house from the
Ascendant, the Moon and Venus -- already reproduces exactly. The single number
on top of it, `total_points`, does not, because nothing says how much each of
the twelve cells is worth.

Twelve unknowns, one equation per chart. Collect enough charts with different
dosha patterns and the weights fall out of a least-squares solve; if the fit
is exact on every chart and the weights land on clean fractions, that is the
rule. If it does not fit, the total is not a linear sum of the grid and this
says so rather than shipping a guess.

    python validation/verify_papasamyam.py

Cost: 50 credits per chart, 36 charts, 1,800 credits.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from fractions import Fraction

sys.path.insert(0, ".")
from astro_engine.chart import BirthData  # noqa: E402
from engine_source import build_chart as build  # noqa: E402
from astro_engine.doshas import PAPA_PLANETS, PAPA_REFERENCES, papasamyam  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402

DELHI = (28.6139, 77.2090)
TZ = "+05:30"
CHART_COUNT = 36

CELLS = [(reference, planet)
         for reference in PAPA_REFERENCES
         for planet, _ in PAPA_PLANETS]

# Clean weights would be sixteenths at worst; anything messier means the total
# is not a plain weighted sum.
DENOMINATOR_LIMIT = 16
FIT_TOLERANCE = 1e-6


def charts() -> list[datetime]:
    """Births spread over years so the slow planets move between them."""
    start = datetime(1970, 3, 11, 7, 20)
    return [start + timedelta(days=int(i * 397.3), hours=i * 5)
            for i in range(CHART_COUNT)]


def row_for(moment: datetime) -> list[int]:
    chart = build(
        BirthData(moment.year, moment.month, moment.day,
                  moment.hour, moment.minute, 0, *DELHI),
        vargas=["D1"], dasha_depth=1, include_doshas=True,
    )
    blocks = chart["doshas"]["papasamyam"]["papa_samyam"]["papa_planet"]
    grid = {(block["name"], entry["name"]): entry["has_dosha"]
            for block in blocks for entry in block["planet_dosha"]}
    return [int(grid[cell]) for cell in CELLS]


def solve(rows: list[list[int]], totals: list[float]) -> list[float] | None:
    """Least squares by normal equations, in plain Python."""
    width = len(CELLS)
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(width)]
           for i in range(width)]
    atb = [sum(r[i] * t for r, t in zip(rows, totals)) for i in range(width)]

    # Gaussian elimination with partial pivoting, with a ridge term so a cell
    # that never varies resolves to zero instead of blowing up.
    for i in range(width):
        ata[i][i] += 1e-9
    matrix = [row[:] + [value] for row, value in zip(ata, atb)]
    for column in range(width):
        pivot = max(range(column, width), key=lambda r: abs(matrix[r][column]))
        if abs(matrix[pivot][column]) < 1e-12:
            return None
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        for row in range(width):
            if row == column:
                continue
            factor = matrix[row][column] / matrix[column][column]
            for k in range(column, width + 1):
                matrix[row][k] -= factor * matrix[column][k]
    return [matrix[i][width] / matrix[i][i] for i in range(width)]


def main() -> int:
    moments = charts()
    answers = run(
        [("papasamyam", {"ayanamsa": 1, "coordinates": f"{DELHI[0]},{DELHI[1]}",
                         "datetime": m.strftime("%Y-%m-%dT%H:%M:%S") + TZ})
         for m in moments],
        "papasamyam",
    )

    rows, totals, grid_failures = [], [], 0
    for moment, answer in zip(moments, answers):
        if isinstance(answer, Exception):
            continue
        data = answer["data"]
        theirs = {(block["name"], entry["name"]): entry["has_dosha"]
                  for block in data["papa_samyam"]["papa_planet"]
                  for entry in block["planet_dosha"]}
        mine = row_for(moment)
        if [int(theirs[cell]) for cell in CELLS] != mine:
            grid_failures += 1
            continue
        rows.append(mine)
        totals.append(float(data["total_points"]))

    print(f"\n{len(rows)} usable charts, {grid_failures} grid mismatches")
    if grid_failures:
        print("  the grid itself disagrees; fix that before fitting the total")
        return 1
    if len(rows) < len(CELLS) + 4:
        print("  not enough charts to solve twelve unknowns")
        return 1

    spread = [len({r[i] for r in rows}) for i in range(len(CELLS))]
    constant = [CELLS[i] for i, s in enumerate(spread) if s == 1]
    if constant:
        print(f"  these cells never varied, so their weight is unidentifiable: "
              f"{constant}")

    weights = solve(rows, totals)
    if weights is None:
        print("  singular system")
        return 1

    residuals = [abs(sum(w * v for w, v in zip(weights, row)) - total)
                 for row, total in zip(rows, totals)]
    worst = max(residuals)
    print(f"worst residual {worst:.6g} over {len(rows)} charts")

    print("\nPAPA_POINTS = {")
    for cell, weight in zip(CELLS, weights):
        clean = Fraction(weight).limit_denominator(DENOMINATOR_LIMIT)
        mark = "" if abs(float(clean) - weight) < 1e-6 else "   # not a clean fraction"
        print(f"    {cell!r}: {float(clean)},{mark}")
    print("}")

    if worst < FIT_TOLERANCE:
        print("\nthe total is a weighted sum of the grid; weights above are exact")
        return 0
    print("\nthe total is NOT a linear sum of the grid -- something else is in it")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
