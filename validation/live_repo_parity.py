"""Compare live response blocks with the checked-in pure rule modules.

The astronomy layer is intentionally not imported here. This catches a stale
deployment or route-specific transformation while using the live chart JSON as
the input to the pure calculators.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astro_engine import ashtakavarga, calendar_points, doshas, matching, numerology, porutham, relationships, yogas


BASE = os.environ.get("ASTRO_ENGINE_URL", "http://192.168.68.114:8000").rstrip("/")
checks = 0
passed = 0
failures: list[str] = []


def check(label, condition, detail=""):
    global checks, passed
    checks += 1
    if condition:
        passed += 1
    else:
        failures.append(f"{label}: {detail}")


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.status, json.loads(response.read())


def chart_payload(day="1990-01-15", clock="04:30", lat=28.6139, lon=77.2090):
    return {
        "date": day, "time": clock, "latitude": lat, "longitude": lon,
        "timezone": "Asia/Kolkata", "reference_time": "2026-09-20T12:00:00",
        "vargas": ["D1", "D2", "D3", "D4", "D7", "D9", "D10", "D12", "D16", "D20", "D24", "D27", "D30", "D40", "D45", "D60"],
        "include_yogas": True, "include_ashtakavarga": True,
        "include_relationships": True, "include_doshas": True,
        "include_calendar": True, "include_nakshatra_info": True,
    }


def main():
    status, chart = post("/v1/chart", chart_payload())
    check("live full chart available", status == 200, str(status))
    if status != 200:
        print(f"{passed}/{checks} checks pass")
        return 1

    expected_av = ashtakavarga.compute(chart)
    check("ashtakavarga pure parity", chart.get("ashtakavarga") == expected_av["ashtakavarga"], "block differs")
    check("sarvashtakavarga pure parity", chart.get("sarvashtakavarga") == expected_av["sarvashtakavarga"], "block differs")

    expected_rel = relationships.compute(chart)
    check("relationships pure parity", chart.get("planet_relationship") == expected_rel, "block differs")

    expected_dosha = doshas.compute(chart)
    check("dosha pure parity", chart.get("doshas") == expected_dosha, "block differs")

    expected_yogas = yogas.report(chart)
    check("yoga pure parity", chart.get("yogas") == expected_yogas, "block differs")

    expected_calendar = calendar_points.compute(chart)
    for key in ("solstice", "drik_ritu", "sudarshana_chakra"):
        check(f"calendar {key} pure parity", chart.get(key) == expected_calendar[key], "block differs")

    status, matching_live = post("/v1/matching", {
        "boy": chart_payload(),
        "girl": chart_payload("1992-06-20", "14:15", 19.0760, 72.8777),
    })
    boy_status, boy = post("/v1/chart", chart_payload())
    girl_status, girl = post("/v1/chart", chart_payload("1992-06-20", "14:15", 19.0760, 72.8777))
    expected_matching = matching.compute(boy, girl)
    check("matching pure parity", status == 200 and matching_live == expected_matching, "block differs")

    porutham_payload = {
        "boy_nakshatra": 9, "boy_nakshatra_pada": 1,
        "girl_nakshatra": 12, "girl_nakshatra_pada": 2, "twelve": True,
    }
    status, porutham_live = post("/v1/porutham", porutham_payload)
    expected_porutham = porutham.compute(9, 1, 12, 2, twelve=True)
    check("porutham pure parity", status == 200 and porutham_live == expected_porutham, "block differs")

    name = numerology.Name("John", "", "Doe")
    num_payload = {
        "first_name": "John", "middle_name": "", "last_name": "Doe",
        "date_of_birth": "2004-02-12", "reference_date": "2026-09-20",
        "additional_vowel": False, "prokerala_compatible": False,
    }
    status, num_live = post("/v1/numerology", num_payload)
    from datetime import date
    expected_num = numerology.report(name, date(2004, 2, 12), reference=date(2026, 9, 20), additional_vowel=False, prokerala_compatible=False)
    check("numerology pure parity", status == 200 and num_live == expected_num, "block differs")

    print(f"{passed}/{checks} deployed-vs-repository pure parity checks pass")
    for failure in failures:
        print(f"  - {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
