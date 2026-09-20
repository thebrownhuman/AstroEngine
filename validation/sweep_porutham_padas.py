"""Find what the last four poruthams use beyond the two nakshatras.

The 729-cell star table is exact at pada 1 and wrong about one case in twenty
elsewhere, so Rasi, Rasi Lord, Vashya and Varna depend on the pada as well.
What they cannot depend on is the *sign*: in every disagreement found so far
both people's signs are identical between the two padas.

Rather than guess at the mechanism, measure it. Take star pairs that are known
to contradict themselves across padas, plus controls that do not, and fetch
all nine pada combinations for each. Nine cells per star pair says directly
whether the answer is a function of the pada pair, of one side's pada only, or
of something finer.

    python validation/sweep_porutham_padas.py

Cost: 9 calls per star pair, 50 credits each.
"""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from astro_engine import porutham as P  # noqa: E402
from astro_engine.constants import NAKSHATRAS  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402
from validation.verify_porutham_signs import job, verdicts  # noqa: E402

RULES = ("Rasi Porutham", "Rasi Lord Porutham",
         "Vashya Porutham", "Varna Porutham")
PADAS = (1, 2, 3)          # pada 4 is Prokerala's off-by-one, excluded

# Star pairs that already contradict themselves across padas, and controls
# that do not. Controls matter: a mechanism that fires everywhere would show
# up as the table being wrong far more often than one case in twenty.
DISAGREEING = [(13, 0), (13, 1), (13, 7), (13, 8), (1, 15), (1, 24), (1, 6)]
CONTROLS = [(0, 0), (5, 10), (20, 3)]


def pada_index(nakshatra: int, pada: int) -> int:
    """Absolute pada, 0-based, the way this engine counts."""
    return nakshatra * 4 + pada - 1


def main() -> int:
    pairs = DISAGREEING + CONTROLS
    jobs, index = [], []
    for girl, boy in pairs:
        for gp in PADAS:
            for bp in PADAS:
                jobs.append(job((girl, gp), (boy, bp)))
                index.append((girl, boy, gp, bp))

    answers = run(jobs, "porutham pada grid")

    table: dict[tuple[int, int], dict[tuple[int, int], dict]] = defaultdict(dict)
    for (girl, boy, gp, bp), answer in zip(index, answers):
        if isinstance(answer, Exception):
            continue
        table[(girl, boy)][(gp, bp)] = verdicts(answer)

    for rule in RULES:
        print(f"\n=== {rule}")
        for girl, boy in pairs:
            grid = table.get((girl, boy), {})
            if len(grid) < len(PADAS) ** 2:
                print(f"   {NAKSHATRAS[girl]}/{NAKSHATRAS[boy]}: incomplete")
                continue
            rows = []
            for gp in PADAS:
                rows.append("".join(str(int(grid[(gp, bp)][rule]))
                                    for bp in PADAS))
            varies = len({c for row in rows for c in row}) > 1
            tag = "VARIES" if varies else "constant"
            print(f"   {NAKSHATRAS[girl]:16}/{NAKSHATRAS[boy]:16} "
                  f"{' '.join(rows)}  {tag}")

    # Does the bride's pada alone explain it, or the groom's, or neither?
    print("\nwhat the variation tracks")
    for rule in RULES:
        girl_only = boy_only = both = 0
        for girl, boy in pairs:
            grid = table.get((girl, boy), {})
            if len(grid) < len(PADAS) ** 2:
                continue
            by_girl = {gp: {grid[(gp, bp)][rule] for bp in PADAS} for gp in PADAS}
            by_boy = {bp: {grid[(gp, bp)][rule] for gp in PADAS} for bp in PADAS}
            girl_constant = all(len(v) == 1 for v in by_girl.values())
            boy_constant = all(len(v) == 1 for v in by_boy.values())
            if girl_constant and not boy_constant:
                girl_only += 1
            elif boy_constant and not girl_constant:
                boy_only += 1
            elif not girl_constant and not boy_constant:
                both += 1
        print(f"   {rule:22} bride's pada only {girl_only}, "
              f"groom's only {boy_only}, both {both}")

    # The obvious candidate: Prokerala counting padas from one instead of zero.
    print("\ndoes an off-by-one in the pada index explain the sign they use?")
    for girl, boy in DISAGREEING[:4]:
        grid = table.get((girl, boy), {})
        if not grid:
            continue
        for gp in PADAS:
            ours = P.rasi_of(girl, gp)
            theirs = (pada_index(girl, gp) + 1) // 9 % 12
            if ours != theirs:
                print(f"   {NAKSHATRAS[girl]} pada {gp}: "
                      f"our sign {ours}, shifted sign {theirs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
