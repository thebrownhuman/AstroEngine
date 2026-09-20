"""Check tara bala and chandra bala against the live API.

Both are shipped on classical rules and were never compared, because the two
endpoints are expensive and a wrong table here is at least visible -- it says
"Vipat" where Prokerala says "Vipat" or it does not. This closes that.

The endpoint names are not in the docs this engine was built from, so the
first pass tries the likely spellings and keeps whichever answers. A 404 is
free; only a 200 costs credits.

    python validation/verify_bala.py

Cost: 50 credits per day per endpoint, eight days, about 800 credits.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
import httpx  # noqa: E402
import swisseph as swe  # noqa: E402

from astro_engine import bala  # noqa: E402
from astro_engine.constants import PROKERALA_NAKSHATRA_NAMES, SIGNS  # noqa: E402
from astro_engine.ephemeris import SiderealScanner, julian_day  # noqa: E402
from validation.parallel_fetch import BASE_URL, live_workers, run  # noqa: E402

DELHI = (28.6139, 77.2090)
TZ = "+05:30"
DAYS = [datetime(2024, 1, 3) + timedelta(days=41 * i) for i in range(8)]

TARA_CANDIDATES = ["tara-bala", "tarabala", "tara-balam"]
CHANDRA_CANDIDATES = ["chandra-bala", "chandrabala", "chandra-balam"]


def params(moment: datetime) -> dict:
    return {"ayanamsa": 1, "coordinates": f"{DELHI[0]},{DELHI[1]}",
            "datetime": moment.strftime("%Y-%m-%dT%H:%M:%S") + TZ}


def discover(candidates: list[str], worker) -> str | None:
    """The first spelling that is not a 404. Costs nothing for the misses."""
    for name in candidates:
        response = httpx.get(
            f"{BASE_URL}/{name}", params=params(DAYS[0]),
            headers={"Authorization": f"Bearer {worker.token()}"}, timeout=60.0,
        )
        if response.status_code != 404:
            print(f"  {name}: HTTP {response.status_code}")
            return name
        print(f"  {name}: 404")
    return None


def _midpoint(window: dict) -> datetime:
    """The instant to evaluate a window at, in local time, naive."""
    begin = datetime.fromisoformat(window["start"]).replace(tzinfo=None)
    finish = datetime.fromisoformat(window["end"]).replace(tzinfo=None)
    return begin + (finish - begin) / 2


def _transit(moment: datetime, arc: float) -> int:
    """Index of the Moon's nakshatra or sign at a local Delhi moment."""
    scanner = SiderealScanner()
    jd = julian_day(moment - timedelta(hours=5.5))
    return int(scanner.longitude(jd, swe.MOON) / arc)


def compare_tara(payload: dict, moment: datetime) -> tuple[int, list[str]]:
    """Each window says which janma stars hold which tara. Check every one."""
    checks, problems = 0, []
    for window in payload["data"]["tara_bala"]:
        index = _transit(_midpoint(window), 360.0 / 27)
        theirs = {star["id"] for star in window["nakshatras"]}
        # The list is every janma star the window actually favours, not the
        # three holding the tara the window is named after.
        ours = {janma for janma in range(27)
                if bala.tara(janma, index)[0] not in bala.HOSTILE_TARAS}
        checks += 1
        if ours != theirs:
            problems.append(
                f"{moment:%Y-%m-%d} {window['name']} under "
                f"{PROKERALA_NAKSHATRA_NAMES[index]}: "
                f"{sorted(ours - theirs)} extra, {sorted(theirs - ours)} missing")
    return checks, problems


def compare_chandra(payload: dict, moment: datetime) -> tuple[int, list[str]]:
    checks, problems = 0, []
    for window in payload["data"]["chandra_bala"]:
        index = _transit(_midpoint(window), 30.0)
        theirs = {sign["id"] for sign in window["rasis"]}
        ours = {janma for janma in range(12) if bala.chandra_bala(janma, index)}
        checks += 1
        if ours != theirs:
            problems.append(
                f"{moment:%Y-%m-%d} Moon in {SIGNS[index]}: "
                f"{sorted(ours - theirs)} extra, {sorted(theirs - ours)} missing")
    return checks, problems


def main() -> int:
    workers = live_workers()
    if not workers:
        raise SystemExit("no usable Prokerala apps")

    print("looking for the endpoints")
    tara_endpoint = discover(TARA_CANDIDATES, workers[0])
    chandra_endpoint = discover(CHANDRA_CANDIDATES, workers[0])
    if not tara_endpoint and not chandra_endpoint:
        print("\nneither endpoint exists under any tried spelling; "
              "tara and chandra bala stay flagged as unchecked")
        return 1

    total_checks, all_problems = 0, []

    for label, endpoint, comparer in (
        ("tara bala", tara_endpoint, compare_tara),
        ("chandra bala", chandra_endpoint, compare_chandra),
    ):
        if endpoint is None:
            print(f"\n{label}: no endpoint, still unchecked")
            continue
        answers = run([(endpoint, params(d)) for d in DAYS], label)
        for moment, answer in zip(DAYS, answers):
            if isinstance(answer, Exception):
                all_problems.append(f"{moment:%Y-%m-%d}: {str(answer)[:90]}")
                continue
            checks, problems = comparer(answer, moment)
            total_checks += checks
            all_problems += problems
        print(f"{label}: {total_checks} checks so far")

    print(f"\n{total_checks - len(all_problems)}/{total_checks} bala checks pass")
    for line in all_problems[:25]:
        print(f"  {line}")
    return 1 if all_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
