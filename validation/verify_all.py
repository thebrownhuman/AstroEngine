"""End-to-end parity sweep across every layer, against the live Prokerala API.

Covers what the per-feature scripts do not: panchanga elements, sunrise and
sunset, and the divisional charts. Everything is cached, so re-runs are free.

    python validation/verify_all.py            # uses cache, reports
    python validation/verify_all.py --fetch    # allows new paid calls

Approximate cost per chart when nothing is cached:
    planet-position  30   panchang  10   mangal-dosha  30
    divisional-planet-position  50 per varga
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from astro_engine import yogas  # noqa: E402
from astro_engine.chart import BirthData  # noqa: E402
from engine_source import build_chart as build  # noqa: E402
from astro_engine.constants import SIGNS  # noqa: E402
from astro_engine.vargas import VARGAS  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

CHARTS = [
    ("Delhi 1990", datetime(1990, 1, 15, 4, 30), 28.6139, 77.2090, "+05:30", 5.5),
    ("Mumbai 1975", datetime(1975, 8, 22, 17, 45), 19.0760, 72.8777, "+05:30", 5.5),
    ("Chennai 2003", datetime(2003, 3, 7, 9, 5), 13.0827, 80.2707, "+05:30", 5.5),
    ("London 1988", datetime(1988, 11, 2, 23, 20), 51.5074, -0.1278, "+00:00", 0.0),
]

# Their chart_type -> our varga key.
VARGA_MAP = {
    "lagna": "D1", "hora": "D2", "drekkana": "D3", "chaturthamsa": "D4",
    "navamsa": "D9", "dasamsa": "D10", "dwadasamsa": "D12", "shodasamsa": "D16",
    "trimsamsa": "D30", "khavedamsa": "D40", "akshavedamsa": "D45",
    "shashtyamsa": "D60",
}

GRAHA_MAP = {
    "Sun": "Sun", "Moon": "Moon", "Mercury": "Mercury", "Venus": "Venus",
    "Mars": "Mars", "Jupiter": "Jupiter", "Saturn": "Saturn",
    "Rahu": "Rahu", "Ketu": "Ketu",
}


class Tally:
    def __init__(self):
        self.results: dict[str, list[bool]] = {}
        self.failures: list[str] = []

    def add(self, area: str, ok: bool, detail: str = ""):
        self.results.setdefault(area, []).append(ok)
        if not ok and detail:
            self.failures.append(f"{area}: {detail}")

    def report(self) -> int:
        print("\n" + "=" * 70)
        print(f"  {'area':34} {'checks':>8} {'pass':>7}  status")
        total = passed = 0
        for area, results in self.results.items():
            hits = sum(results)
            total += len(results)
            passed += hits
            state = "ok" if hits == len(results) else "MISMATCH"
            print(f"  {area:34} {len(results):>8} {hits:>7}  {state}")
        print(f"\n  {passed}/{total} checks pass")
        if self.failures:
            print(f"\n  {len(self.failures)} failure(s):")
            for line in self.failures[:40]:
                print(f"    {line}")
        return 1 if self.failures else 0


def local_of(entry, offset_hours, iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)


def run(tally: Tally):
    for label, moment, lat, lon, tz, offset in CHARTS:
        iso = moment.strftime("%Y-%m-%dT%H:%M:%S") + tz
        coords = f"{lat},{lon}"
        print(f"\n--- {label} ---")

        base = dict(year=moment.year, month=moment.month, day=moment.day,
                    hour=moment.hour, minute=moment.minute, second=0,
                    latitude=lat, longitude=lon)
        chart = build(BirthData(**base), vargas=list(VARGAS), dasha_depth=1)

        # --- planetary longitudes ---
        theirs = fetch("planet-position",
                       {"ayanamsa": 1, "coordinates": coords, "datetime": iso})
        for body in theirs["data"]["planet_position"]:
            name = GRAHA_MAP.get(body["name"])
            if name and name in chart["grahas"]:
                delta = abs(chart["grahas"][name]["longitude"] - body["longitude"]) * 3600
                tally.add("planetary longitude", delta < 0.01,
                          f"{label} {name} off {delta:.4f} arcsec")
            elif body["name"] == "Ascendant":
                delta = abs(chart["lagna"]["longitude"] - body["longitude"]) * 3600
                tally.add("ascendant", delta < 0.01, f"{label} off {delta:.4f} arcsec")
        print(f"  positions: {len(theirs['data']['planet_position'])} bodies")

        # --- panchanga ---
        pk = fetch("panchang", {"ayanamsa": 1, "coordinates": coords, "datetime": iso})["data"]
        mine = chart["panchanga"]

        def active(entries):
            """The element covering the birth instant."""
            for item in entries:
                start = datetime.fromisoformat(item["start"]).replace(tzinfo=None)
                end = datetime.fromisoformat(item["end"]).replace(tzinfo=None)
                if start <= moment < end:
                    return item
            return entries[0]

        their_tithi = active(pk["tithi"])
        their_nak = active(pk["nakshatra"])
        their_yoga = active(pk["yoga"])
        their_karana = active(pk["karana"])

        tally.add("tithi", mine["tithi"]["name"].endswith(their_tithi["name"]),
                  f"{label} {mine['tithi']['name']} vs {their_tithi['name']}")
        tally.add("paksha",
                  mine["tithi"]["paksha"] == their_tithi["paksha"].split()[0],
                  f"{label} {mine['tithi']['paksha']} vs {their_tithi['paksha']}")
        tally.add("nakshatra", mine["nakshatra"]["name"] == their_nak["name"],
                  f"{label} {mine['nakshatra']['name']} vs {their_nak['name']}")
        tally.add("yoga (panchanga)",
                  mine["yoga"]["name"].lower()[:5] == their_yoga["name"].lower()[:5],
                  f"{label} {mine['yoga']['name']} vs {their_yoga['name']}")
        tally.add("karana", mine["karana"]["name"] == their_karana["name"],
                  f"{label} {mine['karana']['name']} vs {their_karana['name']}")
        tally.add("vaara (civil)", mine["civil_vara"]["name"] == pk["vaara"],
                  f"{label} {mine['civil_vara']['name']} vs {pk['vaara']}")

        # --- sunrise and sunset, in their geometric convention ---
        # Their panchang reports the sunrise and sunset OF the requested calendar
        # date. Our chart reports them relative to the birth instant, which is a
        # different question for anyone born after sunrise, so anchor the
        # comparison at local noon on that date.
        from astro_engine.ephemeris import jd_to_datetime, julian_day, sun_rise_set

        shift = timedelta(hours=offset)
        noon_jd = julian_day(datetime.combine(moment.date(), datetime.min.time())
                             + timedelta(hours=12) - shift)
        solar = sun_rise_set(noon_jd, lat, lon, convention="geometric")
        for key, jd_key in (("sunrise", "sunrise_jd"), ("sunset", "sunset_jd")):
            theirs_time = datetime.fromisoformat(pk[key]).replace(tzinfo=None)
            ours_time = jd_to_datetime(solar[jd_key]) + shift
            gap = abs((ours_time - theirs_time).total_seconds())
            tally.add(f"{key} (geometric)", gap <= 5,
                      f"{label} off {gap:.0f}s ({ours_time:%H:%M:%S} vs {theirs_time:%H:%M:%S})")
        print(f"  panchanga + solar: sunrise {pk['sunrise'][11:19]}")

        # --- mangal dosha ---
        md = fetch("mangal-dosha", {"ayanamsa": 1, "coordinates": coords, "datetime": iso})["data"]
        view = yogas.ChartView(chart)
        ours_kuja = yogas.kuja(view).present
        tally.add("mangal dosha", ours_kuja == md["has_dosha"],
                  f"{label} engine={ours_kuja} prokerala={md['has_dosha']}")
        print(f"  mangal dosha: engine={ours_kuja} prokerala={md['has_dosha']}")

        # --- divisional charts ---
        for chart_type, key in VARGA_MAP.items():
            try:
                dv = fetch("divisional-planet-position", {
                    "ayanamsa": 1, "coordinates": coords, "datetime": iso,
                    "chart_type": chart_type,
                })["data"]
            except Exception as exc:
                print(f"  {chart_type}: skipped ({str(exc)[:60]})")
                continue
            ours = chart["vargas"][key]["grahas"]
            checked = 0
            for house in dv["divisional_positions"]:
                for entry in house["planet_positions"]:
                    name = GRAHA_MAP.get(entry["planet"]["name"])
                    if not name or name not in ours:
                        continue
                    same = SIGNS[ours[name]["sign"]["index"]] == entry["rasi"]["name"]
                    tally.add(f"varga {key}", same,
                              f"{label} {name}: {SIGNS[ours[name]['sign']['index']]} "
                              f"vs {entry['rasi']['name']}")
                    checked += 1
            print(f"  {chart_type:14} ({key}): {checked} placements")


def main() -> int:
    tally = Tally()
    run(tally)
    return tally.report()


if __name__ == "__main__":
    raise SystemExit(main())
