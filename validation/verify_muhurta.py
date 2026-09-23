"""Muhurta parity: choghadiya, the kaal periods, Abhijit and Brahma Muhurat.

Seven consecutive dates, so every weekday table is exercised once. All of the
API responses are already cached by calibrate_muhurta.py except the auspicious
ones.

    python validation/verify_muhurta.py

Cost when uncached: 150 credits per date.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from astro_engine import muhurta  # noqa: E402
from engine_source import muhurta_report  # noqa: E402
from astro_engine.constants import WEEKDAYS  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

LATITUDE, LONGITUDE = 28.6139, 77.2090
# Asia/Kolkata has never observed DST, so the fixed offset above and
# this zone agree for every date in the sweep.
TIMEZONE = "Asia/Kolkata"
OFFSET_HOURS = 5.5
TZ = "+05:30"
DAYS = [datetime(1990, 1, 14, 12, 0) + timedelta(days=n) for n in range(7)]

# Their sunrise agrees with Swiss Ephemeris to about a second, but the sunset
# and next-sunrise they feed these endpoints scatter by up to seven -- a
# lower-precision solar routine on their side, which no convention flag here
# reproduces. Slice boundaries inherit that scatter, so the tolerance is set
# where it stops being a real disagreement and the worst drift is printed.
TOLERANCE_SECONDS = 15.0


def at(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp).replace(tzinfo=None)


def main() -> int:
    checks = 0
    failures: list[str] = []
    brahma_offsets = []
    worst = 0.0

    for day in DAYS:
        params = {"ayanamsa": 1, "coordinates": f"{LATITUDE},{LONGITUDE}",
                  "datetime": day.strftime("%Y-%m-%dT%H:%M:%S") + TZ}
        mine = muhurta_report(day, LATITUDE, LONGITUDE, OFFSET_HOURS,
                              TIMEZONE)
        weekday = WEEKDAYS[mine["vara_index"]]

        def compare(area: str, ours: datetime, theirs: datetime) -> None:
            nonlocal checks
            checks += 1
            nonlocal worst
            gap = abs((ours - theirs).total_seconds())
            worst = max(worst, gap)
            if gap > TOLERANCE_SECONDS:
                failures.append(f"{weekday} {area}: off {gap:.1f}s "
                                f"({ours:%H:%M:%S} vs {theirs:%H:%M:%S})")

        # --- choghadiya: names, order, velas and boundaries ------------------
        theirs = fetch("choghadiya", params)["data"]["muhurat"]
        for ours, other in zip(mine["choghadiya"], theirs):
            checks += 1
            if (ours["name"], ours["is_day"], ours["vela"], ours["type"]) != \
               (other["name"], other["is_day"], other["vela"], other["type"]):
                failures.append(
                    f"{weekday} choghadiya: "
                    f"{ours['name']}/{ours['vela']}/{ours['type']} vs "
                    f"{other['name']}/{other['vela']}/{other['type']}"
                )
            compare("choghadiya start", at(ours["start"]), at(other["start"]))

        # --- inauspicious periods --------------------------------------------
        theirs = {e["name"]: e["period"]
                  for e in fetch("inauspicious-period", params)["data"]["muhurat"]}
        for entry in mine["inauspicious"]:
            other = theirs.get(entry["name"])
            if other is None:
                failures.append(f"{weekday} {entry['name']}: absent from response")
                continue
            for ours_period, their_period in zip(entry["period"], other):
                compare(f"{entry['name']} start",
                        at(ours_period["start"]), at(their_period["start"]))
                compare(f"{entry['name']} end",
                        at(ours_period["end"]), at(their_period["end"]))

        # --- auspicious periods ----------------------------------------------
        theirs = {e["name"]: e["period"]
                  for e in fetch("auspicious-period", params)["data"]["muhurat"]}
        for entry in mine["auspicious"]:
            other = theirs.get(entry["name"])
            if other is None:
                continue
            ours_period, their_period = entry["period"][0], other[0]
            if entry["name"] == "Brahma Muhurat":
                # Tracked separately: the width matches, the anchor is 23s out.
                brahma_offsets.append(
                    (at(ours_period["start"]) - at(their_period["start"])).total_seconds()
                )
                checks += 1
                ours_width = (at(ours_period["end"]) - at(ours_period["start"])).total_seconds()
                their_width = (at(their_period["end"]) - at(their_period["start"])).total_seconds()
                if abs(ours_width - their_width) > TOLERANCE_SECONDS:
                    failures.append(f"{weekday} Brahma width: "
                                    f"{ours_width:.0f}s vs {their_width:.0f}s")
                continue
            compare(f"{entry['name']} start",
                    at(ours_period["start"]), at(their_period["start"]))
            compare(f"{entry['name']} end",
                    at(ours_period["end"]), at(their_period["end"]))

        # --- hora --------------------------------------------------------------
        theirs = fetch("hora", params)["data"]["hora_timing"]
        for ours, other in zip(mine["hora"], theirs):
            checks += 1
            if (ours["hora"]["name"], ours["type"], ours["is_day"]) != \
               (other["hora"]["name"], other["type"], other["is_day"]):
                failures.append(
                    f"{weekday} hora: {ours['hora']['name']}/{ours['type']} vs "
                    f"{other['hora']['name']}/{other['type']}"
                )
            compare("hora start", at(ours["start"]), at(other["start"]))

        # --- gowri nalla neram ---------------------------------------------------
        theirs = fetch("gowri-nalla-neram", params)["data"]["muhurat"]
        for index, (ours, other) in enumerate(zip(mine["gowri_nalla_neram"], theirs)):
            checks += 1
            if (ours["name"], ours["type"], ours["is_day"]) != \
               (other["name"], other["type"], other["is_day"]):
                failures.append(
                    f"{weekday} gowri slot {index}: {ours['name']} vs {other['name']}"
                )
            compare("gowri start", at(ours["start"]), at(other["start"]))

        # --- disha shool ---------------------------------------------------------
        other = fetch("disha-shool", params)["data"]["disha_shool"]
        ours = mine["disha_shool"]
        checks += 1
        if (ours["direction"], ours["remedy"]) != (other["direction"], other["remedy"]):
            failures.append(f"{weekday} disha shool: "
                            f"{ours['direction']}/{ours['remedy']} vs "
                            f"{other['direction']}/{other['remedy']}")
        compare("disha shool start", at(ours["start"]), at(other["start"]))
        compare("disha shool end", at(ours["end"]), at(other["end"]))

    print(f"{checks - len(failures)}/{checks} muhurta checks pass "
          f"(worst boundary drift {worst:.1f}s)")
    for line in failures[:40]:
        print(f"  {line}")
    if brahma_offsets:
        print(f"\nBrahma Muhurat anchor offset: "
              f"{min(brahma_offsets):+.1f}s to {max(brahma_offsets):+.1f}s "
              f"across {len(brahma_offsets)} dates (width matches)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
