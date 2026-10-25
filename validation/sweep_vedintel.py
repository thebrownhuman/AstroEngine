"""Fetch VedIntel answers for the coverage births, as a second reference.

Same nineteen births as sweep_coverage.py. Cached under
validation/.cache/vedintel; re-runs are free.

    python validation/sweep_vedintel.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")
from validation.sweep_coverage import births  # noqa: E402
from validation.vedintel import OutOfCalls, cache_path, fetch  # noqa: E402
import validation.vedintel as vedintel  # noqa: E402

PER_BIRTH = [
    ("horoscope/planet-details", {}),
    ("horoscope/divisional-charts", {"chart_id": 9}),
    ("horoscope/ashtakvarga", {}),
    ("horoscope/binnashtakvarga", {}),
    ("extended-horoscope/kp-houses", {}),
    ("extended-horoscope/kp-planets", {}),
    ("extended-horoscope/friendship-table", {}),
    ("extended-horoscope/yoga-list", {}),
    ("dashas/mahadasha", {}),
    ("dosha/kaalsarp-dosh", {}),
    ("dosha/mangal-dosh", {}),
]


def tz_hours(moment, zone) -> float:
    # Exact, seconds included: local mean time zones such as Calcutta's
    # +05:53:20 lose 20 s, and the lagna moves 5', if cut to the minute.
    from zoneinfo import ZoneInfo
    return round(moment.replace(tzinfo=ZoneInfo(zone)).utcoffset().total_seconds() / 3600, 6)


def birth_params(moment, lat, lon, zone) -> dict:
    return {"dob": moment.strftime("%d/%m/%Y"), "tob": moment.strftime("%H:%M"),
            "lat": lat, "lon": lon, "tz": tz_hours(moment, zone)}


# VedIntel supports 1800-2027 only.
def supported_births():
    return [b for b in births() if 1800 <= b[1].year <= 2027]


def pair_params(boy, girl) -> dict:
    def side(birth):
        params = birth_params(*birth[1:])
        if params["tz"] == 0:
            params["tz"] = 0.000001     # VedIntel reads tz=0 as missing
        return params
    return {**side(boy), **{"f_" + k: v for k, v in side(girl).items()}}


def pairs():
    people = supported_births()
    return list(zip(people, people[1:]))


def jobs() -> list[tuple[str, dict]]:
    out = []
    for _, moment, lat, lon, zone in supported_births():
        base = birth_params(moment, lat, lon, zone)
        for endpoint, extra in PER_BIRTH:
            out.append((endpoint, {**base, **extra}))
    for boy, girl in pairs():
        out.append(("matching/north-match", pair_params(boy, girl)))
    return out


def main() -> int:
    todo = jobs()
    missing = [j for j in todo if not cache_path(*j).exists()]
    print(f"{len(todo)} jobs, {len(missing)} to fetch")
    failed = 0
    for endpoint, params in missing:
        try:
            payload = fetch(endpoint, params)
        except OutOfCalls as exc:
            print(f"stopped: {exc}")
            break
        if payload.get("status") != 200:
            failed += 1
            print(f"  {endpoint} {params['dob']}: {str(payload)[:150]}")
    print(f"done; {failed} failed; calls left on current key: {vedintel.remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
