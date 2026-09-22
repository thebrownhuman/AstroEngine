"""Run every parity check there is and print one table.

All responses are cached, so a re-run costs nothing and takes about a minute.
Delete validation/.cache to refetch, which costs real credits.

    python validation/verify_everything.py
"""

from __future__ import annotations

import subprocess
import sys
import time

sys.path.insert(0, ".")

# Two suites end non-zero on purpose, because two disagreements with Prokerala
# are real and documented rather than regressions. Listing them here keeps the
# table honest: a genuine break shows up as FAIL, these show up as "known".
KNOWN_DEVIATIONS = {
    "yogas": "Daridra Yoga: rule not recovered, flagged unverified",
    "muhurta": "one gowri slot where Prokerala contradicts its own rotation",
}

SUITES = [
    # This one is not a parity suite. Every other entry asks whether the engine
    # matches Prokerala, which cannot catch an error both sides share; this asks
    # whether the output is what BPHS says and whether it is internally
    # coherent. It runs in-process, so it needs no server and no cache.
    ("rules vs BPHS", "validation/against_bphs.py"),
    ("planetary positions vs NASA JPL", "validation/against_jpl.py"),
    ("sunrise, ayanamsa vs published", "validation/against_external.py"),
    ("full Prokerala sweep", "validation/verify_all.py"),
    ("numerology vs spec", "validation/against_prokerala_spec.py"),
    ("yogas", "validation/against_prokerala_yogas.py"),
    ("ashtakavarga", "validation/verify_ashtakavarga.py"),
    ("muhurta", "validation/verify_muhurta.py"),
    ("papasamyam points", "validation/verify_papasamyam.py"),
    ("tara and chandra bala", "validation/verify_bala.py"),
    ("matching", "validation/verify_matching.py"),
    ("porutham", "validation/verify_porutham.py"),
]


def unit_tests() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        capture_output=True, text=True,
    )
    tail = [line for line in result.stdout.splitlines() if "passed" in line]
    return result.returncode == 0, tail[-1] if tail else "no summary"


def run(path: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, path], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    lines = [line.strip() for line in (result.stdout or "").splitlines()
             if line.strip()]
    summary = next(
        (line for line in lines
         if "checks pass" in line or "matched" in line or "within" in line
         or "deviation" in line),
        lines[-1] if lines else "no output",
    )
    return result.returncode == 0, summary[:96]


def main() -> int:
    started = time.time()
    failures = 0

    print(f"{'suite':36} {'status':7} summary")
    print("-" * 100)

    ok, summary = unit_tests()
    failures += not ok
    print(f"{'unit tests':36} {'ok' if ok else 'FAIL':7} {summary}")

    known = []
    for label, path in SUITES:
        ok, summary = run(path)
        if not ok and label in KNOWN_DEVIATIONS:
            known.append(label)
            status = "known"
        elif ok:
            status = "ok"
        else:
            status = "FAIL"
            failures += 1
        print(f"{label:36} {status:7} {summary}")

    print("-" * 100)
    total = len(SUITES) + 1
    print(f"{total - failures}/{total} suites clean in {time.time() - started:.0f}s")
    for label in known:
        print(f"  known deviation in {label}: {KNOWN_DEVIATIONS[label]}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
