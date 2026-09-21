"""Independent live API contract and invariant sweep.

This script deliberately does not import the engine. It exercises the deployed
HTTP contract as a client would, so it can catch errors hidden by local unit
tests or by comparing implementation output to itself.

    python validation/live_api_audit.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime


BASE = os.environ.get("ASTRO_ENGINE_URL", "http://192.168.68.114:8000").rstrip("/")
VARGAS = [
    "D1", "D2", "D3", "D4", "D7", "D9", "D10", "D12",
    "D16", "D20", "D24", "D27", "D30", "D40", "D45", "D60",
]
GRAHAS = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}
VIMSHOTTARI = [("Sun", 6), ("Moon", 10), ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17), ("Ketu", 7), ("Venus", 20)]
NAKSHATRA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"] * 3
NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
    "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
AYANAMSAS = {"fagan_bradley", "krishnamurti", "lahiri", "lahiri_1940", "raman", "true_chitra", "true_revati", "yukteshwar"}

checks = 0
passed = 0
failures: list[str] = []
requests_made = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks, passed
    checks += 1
    if condition:
        passed += 1
    else:
        failures.append(f"{label}: {detail}" if detail else label)


def call(method: str, path: str, payload=None, query=None):
    global requests_made
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    requests_made += 1
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        content_type = exc.headers.get("content-type", "")
    except Exception as exc:
        return 0, {"error": repr(exc)}, ""
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        parsed = raw.decode("utf-8", errors="replace")
    return status, parsed, content_type


def good(status: int, label: str, body=None):
    check(label, status == 200, f"HTTP {status}: {str(body)[:240]}")
    return body if status == 200 else {}


def chart_payload(**overrides):
    payload = {
        "date": "1990-01-15",
        "time": "04:30",
        "place": "Delhi",
        "timezone": "Asia/Kolkata",
        "reference_time": "2026-09-20T12:00:00",
        "dasha_depth": 4,
        "vargas": VARGAS,
        "prokerala_compatible": True,
        "include_yogas": True,
        "include_transits": True,
        "include_ashtakavarga": True,
        "include_upagrahas": True,
        "include_relationships": True,
        "include_doshas": True,
        "include_calendar": True,
        "include_nakshatra_info": True,
    }
    payload.update(overrides)
    return payload


def test_health_and_openapi():
    status, health, _ = call("GET", "/health")
    health = good(status, "GET /health", health)
    check("health status", health.get("status") == "ok", repr(health))
    check("health version", isinstance(health.get("version"), str), repr(health))
    check("health ephemeris", health.get("ephemeris") == "swieph", repr(health))
    check("health ayanamsas", set(health.get("ayanamsas", [])) == AYANAMSAS, repr(health))
    check("health vargas", health.get("vargas") == VARGAS, repr(health))

    status, spec, _ = call("GET", "/openapi.json")
    spec = good(status, "GET /openapi.json", spec)
    paths = spec.get("paths", {})
    expected = {
        "/v1/chart", "/v1/chart/summary", "/v1/yogas", "/v1/transits",
        "/v1/ashtakavarga", "/v1/upagrahas", "/v1/doshas", "/v1/nakshatra",
        "/v1/sudarshana", "/v1/relationships", "/v1/kp", "/v1/matching",
        "/v1/porutham", "/v1/muhurta", "/v1/bala", "/v1/numerology",
        "/v1/places", "/v1/timezone", "/v1/tool-definition", "/v1/tool-definitions",
        "/health",
    }
    check("OpenAPI route inventory", set(paths) == expected, f"missing={expected-set(paths)}, extra={set(paths)-expected}")
    for path in expected - {"/health", "/v1/places", "/v1/timezone", "/v1/tool-definition", "/v1/tool-definitions"}:
        check(f"OpenAPI POST declared {path}", "post" in paths.get(path, {}), repr(paths.get(path)))


def test_chart_invariants(chart, expect_optional=True, expected_vargas=None):
    check("chart top-level engine", isinstance(chart.get("engine"), dict), repr(chart.get("engine")))
    engine = chart.get("engine", {})
    check("chart sidereal", engine.get("zodiac") == "sidereal", repr(engine))
    check("chart whole-sign houses", engine.get("house_convention") == "whole_sign", repr(engine))
    check("chart ayanamsa", engine.get("ayanamsa") in AYANAMSAS, repr(engine))
    grahas = chart.get("grahas", {})
    check("nine grahas", set(grahas) == GRAHAS, repr(sorted(grahas)))
    for name, body in grahas.items():
        lon = body.get("longitude")
        sign_index = body.get("sign_index")
        check(f"{name} longitude range", isinstance(lon, (int, float)) and 0 <= lon < 360, repr(lon))
        check(f"{name} sign index", sign_index == int(lon // 30) if isinstance(lon, (int, float)) else False, repr(body))
        check(f"{name} degree range", 0 <= body.get("degree_in_sign", -1) < 30, repr(body.get("degree_in_sign")))
        check(f"{name} house range", body.get("house") in range(1, 13), repr(body.get("house")))
        check(f"{name} nakshatra index", body.get("nakshatra_index") in range(27), repr(body.get("nakshatra_index")))
        check(f"{name} nakshatra pada", body.get("nakshatra_pada") in range(1, 5), repr(body.get("nakshatra_pada")))
        check(f"{name} DMS present", isinstance(body.get("dms"), str), repr(body.get("dms")))
    check("lagna longitude range", 0 <= chart.get("lagna", {}).get("longitude", -1) < 360, repr(chart.get("lagna")))
    cusps = chart.get("cusps", [])
    check("12 house cusps", len(cusps) == 12, repr(cusps))
    check("midheaven present", isinstance(chart.get("midheaven"), dict), repr(chart.get("midheaven")))

    houses = chart.get("houses", [])
    check("12 houses", len(houses) == 12, repr(houses))
    check("house numbers unique", [h.get("house") for h in houses] == list(range(1, 13)), repr(houses))
    occupants = {name: body.get("house") for name, body in grahas.items()}
    for house in houses:
        listed = set(house.get("occupants", []))
        expected = {name for name, h in occupants.items() if h == house.get("house")}
        check(f"house {house.get('house')} occupants", listed == expected, f"{listed} != {expected}")

    aspects = chart.get("aspects", [])
    check("nine aspect rows", len(aspects) == 9, repr(aspects))
    for row in aspects:
        check(f"aspect graha {row.get('graha')}", row.get("graha") in GRAHAS, repr(row))
        check(f"aspect houses {row.get('graha')}", all(h in range(1, 13) for h in row.get("aspects_houses", [])), repr(row))

    vargas = chart.get("vargas", {})
    if expected_vargas is None:
        expected_vargas = set(VARGAS) if expect_optional else {"D1", "D9", "D10", "D12", "D30"}
    else:
        expected_vargas = set(expected_vargas)
    check("requested vargas returned", set(vargas) == expected_vargas, f"got={sorted(vargas)}, expected={sorted(expected_vargas)}")
    for key, value in vargas.items():
        check(f"{key} varga grahas", set(value.get("grahas", {})) == GRAHAS, repr(value))
        check(f"{key} varga lagna", isinstance(value.get("lagna"), dict), repr(value))

    dasha = chart.get("dasha", {})
    check("dasha method", dasha.get("system") == "Vimshottari", repr(dasha.get("system")))
    periods = dasha.get("mahadasha", dasha.get("mahadashas", []))
    if periods:
        check("dasha nine mahadashas", len(periods) >= 9, f"count={len(periods)}")
        names = [p.get("lord") for p in periods[:9]]
        birth_lord = dasha.get("birth_dasha_lord")
        start = next((i for i, (name, _) in enumerate(VIMSHOTTARI) if name == birth_lord), 0)
        expected_cycle = VIMSHOTTARI[start:] + VIMSHOTTARI[:start]
        check("dasha lords/order", names == [name for name, _ in expected_cycle], f"birth={birth_lord}, got={names}, expected={[name for name, _ in expected_cycle]}")
        durations = [p.get("duration_years") for p in periods[:9]]
        expected_durations = [years for _, years in expected_cycle]
        check("dasha duration/order", durations == expected_durations, f"got={durations}, expected={expected_durations}")
        check("dasha top-level periods chronological", all(periods[i].get("start", "") < periods[i].get("end", "") for i in range(min(9, len(periods)))), f"got={[(p.get('start'), p.get('end')) for p in periods[:9]]}")
    check("current dasha present", isinstance(chart.get("current_dasha"), dict), f"type={type(chart.get('current_dasha')).__name__}")

    panchanga = chart.get("panchanga", {})
    for key in ("tithi", "nakshatra", "yoga", "karana"):
        check(f"panchanga {key}", isinstance(panchanga.get(key), dict), repr(panchanga))
    moon = grahas.get("Moon", {})
    ni = moon.get("nakshatra_index")
    if ni in range(27):
        check("Moon nakshatra name/index", moon.get("nakshatra") == NAKSHATRA_NAMES[ni], repr(moon))
        check("Moon nakshatra lord/index", moon.get("nakshatra_lord") == NAKSHATRA_LORDS[ni], repr(moon))
    if expect_optional:
        for key in ("ashtakavarga", "sarvashtakavarga", "upagrahas", "planet_relationship", "doshas", "solstice", "drik_ritu", "sudarshana_chakra", "nakshatra_info", "transits", "yogas"):
            check(f"optional block {key}", key in chart, f"keys={sorted(chart)}")


def test_deep_blocks(chart):
    """Check relationships, transit, yoga, wheel, and Sun-derived formulas independently."""
    relationships = chart.get("planet_relationship", {})
    for key in ("natural_relationship", "temporal_relationship", "compound_relationship"):
        rows = relationships.get(key, [])
        check(f"{key} 100 ordered pairs", len(rows) == 100, repr(rows[:2]))
        diagonal = [row for row in rows if row.get("first_planet", {}).get("name") == row.get("second_planet", {}).get("name")]
        check(f"{key} diagonal rows", len(diagonal) == 10, repr(diagonal[:2]))

    transits = chart.get("transits", {})
    positions = transits.get("positions", {})
    check("transit nine positions", isinstance(positions, dict) and len(positions) == 9, repr(positions))
    check("transit names unique", len(set(positions)) == 9, repr(positions))
    for name, position in positions.items():
        check(f"transit longitude {name}", 0 <= position.get("longitude", -1) < 360, repr(position))
    check("transit sade sati block", isinstance(transits.get("sade_sati"), dict), f"type={type(transits.get('sade_sati')).__name__}")
    check("transit saturn afflictions block", isinstance(transits.get("saturn_afflictions"), dict), f"type={type(transits.get('saturn_afflictions')).__name__}")
    returns = transits.get("returns", {})
    check("transit returns block", isinstance(returns, dict) and set(returns) == {"jupiter", "saturn"}, repr(returns))
    for name, events in returns.items():
        check(f"{name} return list", isinstance(events, list), repr(events))
        for event in events:
            check(f"{name} return timestamp", isinstance(event.get("exact"), str), repr(event))
            check(f"{name} return age", isinstance(event.get("age_years"), (int, float)) and event.get("age_years") >= 0, repr(event))
    for key in ("dhaiyya", "kantaka_shani", "ashtama_shani"):
        periods = transits.get("saturn_afflictions", {}).get(key, {}).get("periods", [])
        check(f"{key} periods are objects", all(isinstance(period, dict) for period in periods), repr(periods[:1]))

    yoga_groups = chart.get("yogas", {}).get("yoga_details", [])
    yoga_rows = [item for group in yoga_groups for item in group.get("yoga_list", [])]
    check("24 yoga definitions", len(yoga_rows) == 24, repr(yoga_rows))
    check("yoga names unique", len({item.get("name") for item in yoga_rows}) == 24, repr(yoga_rows))
    check("yoga present count", chart.get("yogas", {}).get("total_present") == sum(bool(item.get("has_yoga")) for item in yoga_rows), repr(chart.get("yogas")))
    kem = {item.get("name"): item for item in yoga_rows if item.get("name") in {"Kemadruma Yoga", "Kemdrum Yoga"}}
    if len(kem) == 2:
        check("duplicate Kemadruma spellings agree", kem["Kemadruma Yoga"].get("has_yoga") == kem["Kemdrum Yoga"].get("has_yoga"), repr(kem))

    wheels = chart.get("sudarshana_chakra", {})
    check("three Sudarshana wheels", set(wheels) == {"Lagna", "Sun", "Moon"}, repr(wheels))
    for name, wheel in wheels.items():
        houses = wheel.get("houses", [])
        check(f"{name} Sudarshana 12 houses", len(houses) == 12, repr(houses))
        check(f"{name} Sudarshana sequence", [h.get("house") for h in houses] == list(range(1, 13)), repr(houses))

    sun = chart.get("grahas", {}).get("Sun", {}).get("longitude")
    upagrahas = {item.get("name"): item.get("longitude") for item in chart.get("upagrahas", [])}
    if isinstance(sun, (int, float)) and len(upagrahas) >= 5:
        expected = {
            "Dhuma": (sun + 133 + 20 / 60) % 360,
        }
        expected["Vyatipata"] = (360 - expected["Dhuma"]) % 360
        expected["Parivesha"] = (expected["Vyatipata"] + 180) % 360
        expected["Indrachapa"] = (360 - expected["Parivesha"]) % 360
        expected["Upaketu"] = (expected["Indrachapa"] + 16 + 40 / 60) % 360
        for name, value in expected.items():
            actual = upagrahas.get(name, -999)
            delta = abs((actual - value + 180) % 360 - 180)
            check(f"Sun-derived upagraha {name}", delta < 1e-6, f"actual={actual}, expected={value}")

    # Independent Kaal Sarpa geometry: all seven visible grahas must lie
    # strictly inside one of the two arcs between Rahu and Ketu.
    grahas = chart.get("grahas", {})
    longs = {name: grahas.get(name, {}).get("longitude") for name in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")}
    rahu = grahas.get("Rahu", {}).get("longitude")
    ketu = grahas.get("Ketu", {}).get("longitude")
    doshas = chart.get("doshas", {})
    if all(isinstance(value, (int, float)) for value in (*longs.values(), rahu, ketu)):
        def hemmed(start, end):
            span = (end - start) % 360.0
            return all(0 < (value - start) % 360.0 < span for value in longs.values())
        forward = hemmed(rahu, ketu)
        reverse = hemmed(ketu, rahu)
        ks = doshas.get("kaal_sarpa", {})
        check("Kaal Sarpa geometry", ks.get("has_dosha") == (forward or reverse), repr(ks))
        expected_direction = "forward" if forward else "reverse" if reverse else None
        check("Kaal Sarpa direction", ks.get("direction") == expected_direction, repr(ks))
        if forward:
            house = grahas["Rahu"].get("house")
            expected_types = ["Anant", "Kulik", "Vaasuki", "Shankhpal", "Padam", "Mahapadam", "Takshak", "Karkotak", "Shankhchurn", "Paatak", "Vishakt", "Sheshnaag"]
            check("Kaal Sarpa type", ks.get("type") == expected_types[house - 1], repr(ks))
        else:
            check("Kaal Amrita type empty", ks.get("type") is None, repr(ks))

    papa = doshas.get("papasamyam", {})
    blocks = papa.get("papa_samyam", {}).get("papa_planet", [])
    check("Papasamyam three references", len(blocks) == 3, repr(blocks))
    weights = {"Ascendant": 1.0, "Moon": 0.5, "Venus": 0.25}
    total = 0.0
    for block in blocks:
        entries = block.get("planet_dosha", [])
        check(f"Papasamyam {block.get('name')} four planets", len(entries) == 4, repr(entries))
        total += weights.get(block.get("name"), 0.0) * sum(bool(entry.get("has_dosha")) for entry in entries)
        for entry in entries:
            check(f"Papasamyam position {block.get('name')}/{entry.get('name')}", entry.get("position") in range(1, 13), repr(entry))
    check("Papasamyam weighted total", abs(total - papa.get("total_points", -999)) < 1e-9, repr(papa))


def varga_sign(longitude, key):
    """Independent BPHS-style oracle for the 16 sign-mapping functions."""
    longitude %= 360.0
    sign = int(longitude // 30.0)
    deg = longitude % 30.0
    odd = sign % 2 == 0
    modality = sign % 3
    element = sign % 4
    if key == "D1": return sign
    if key == "D2": return 4 if (odd == (deg < 15.0)) else 3
    if key == "D3": return (sign + 4 * int(deg // 10.0)) % 12
    if key == "D4": return (sign + 3 * int(deg // 7.5)) % 12
    if key == "D7": return ((sign if odd else (sign + 6) % 12) + int(deg // (30.0 / 7.0))) % 12
    if key == "D9": return int(longitude // (30.0 / 9.0)) % 12
    if key == "D10": return ((sign if odd else (sign + 8) % 12) + int(deg // 3.0)) % 12
    if key == "D12": return (sign + int(deg // 2.5)) % 12
    if key == "D16": return ((0 if modality == 0 else 4 if modality == 1 else 8) + int(deg // 1.875)) % 12
    if key == "D20": return ((0 if modality == 0 else 8 if modality == 1 else 4) + int(deg // 1.5)) % 12
    if key == "D24": return ((4 if odd else 3) + int(deg // 1.25)) % 12
    if key == "D27": return ((0 if element == 0 else 3 if element == 1 else 6 if element == 2 else 9) + int(deg // (30.0 / 27.0))) % 12
    if key == "D30":
        table = [(5.0, 0), (10.0, 10), (18.0, 8), (25.0, 2), (30.0, 6)] if odd else [(5.0, 1), (12.0, 5), (20.0, 11), (25.0, 9), (30.0, 7)]
        return next(value for upper, value in table if deg < upper)
    if key == "D40": return ((0 if odd else 6) + int(deg // 0.75)) % 12
    if key == "D45": return ((0 if modality == 0 else 4 if modality == 1 else 8) + int(deg // (30.0 / 45.0))) % 12
    if key == "D60": return (sign + int(deg // 0.5)) % 12
    raise ValueError(key)


def test_varga_math(chart):
    positions = {name: body.get("longitude") for name, body in chart.get("grahas", {}).items()}
    positions["Lagna"] = chart.get("lagna", {}).get("longitude")
    for key, table in chart.get("vargas", {}).items():
        for name, longitude in positions.items():
            expected = varga_sign(longitude, key)
            actual = table.get("lagna", {}).get("index") if name == "Lagna" else table.get("grahas", {}).get(name, {}).get("sign", {}).get("index")
            check(f"{key} {name} independent sign", actual == expected, f"actual={actual}, expected={expected}")


def test_chart_routes():
    full = chart_payload()
    status, chart, _ = call("POST", "/v1/chart", full)
    chart = good(status, "POST /v1/chart full", chart)
    test_chart_invariants(chart)
    test_varga_math(chart)
    test_deep_blocks(chart)

    # Same chart through the coordinate path, timezone derivation path, true nodes,
    # every supported ayanamsa, and each dasha depth.
    coord = {k: v for k, v in full.items() if k not in {"place", "timezone"}}
    coord.update({"latitude": 28.6139, "longitude": 77.2090})
    for label, overrides in [
        ("coordinates", coord),
        ("true nodes", {**coord, "node_type": "true"}),
        ("default flags", {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139, "longitude": 77.2090}),
    ]:
        status, body, _ = call("POST", "/v1/chart", overrides)
        body = good(status, f"POST /v1/chart {label}", body)
        if body:
            test_chart_invariants(body, expect_optional=(label != "default flags"))
    for ayanamsa in sorted(AYANAMSAS):
        status, body, _ = call("POST", "/v1/chart", {**coord, "ayanamsa": ayanamsa, "include_yogas": False})
        body = good(status, f"chart ayanamsa {ayanamsa}", body)
        check(f"ayanamsa echoed {ayanamsa}", body.get("engine", {}).get("ayanamsa") == ayanamsa, repr(body.get("engine")))
    for depth in range(1, 5):
        status, body, _ = call("POST", "/v1/chart", {**coord, "dasha_depth": depth})
        good(status, f"chart dasha depth {depth}", body)

    route_payloads = {
        "/v1/chart/summary": full,
        "/v1/yogas": full,
        "/v1/transits": full,
        "/v1/ashtakavarga": full,
        "/v1/upagrahas": full,
        "/v1/doshas": full,
        "/v1/nakshatra": full,
        "/v1/sudarshana": full,
        "/v1/relationships": full,
        "/v1/kp": full,
    }
    route_bodies = {}
    for path, payload in route_payloads.items():
        status, body, _ = call("POST", path, payload)
        route_bodies[path] = good(status, f"POST {path}", body)
    expected_keys = {
        "/v1/chart/summary": {"summary", "engine", "input"},
        "/v1/yogas": {"engine", "input", "lagna", "yogas"},
        "/v1/transits": {"engine", "input", "natal_moon", "transits",
                         "source", "authority"},
        "/v1/ashtakavarga": {"engine", "input", "lagna", "ashtakavarga",
                             "ashtakavarga_source", "sarvashtakavarga"},
        "/v1/upagrahas": {"engine", "input", "solar_day", "upagrahas"},
        "/v1/doshas": {"engine", "input", "doshas"},
        "/v1/nakshatra": {"engine", "input", "nakshatra", "additional_info"},
        "/v1/sudarshana": {"engine", "input", "solstice", "drik_ritu", "sudarshana_chakra"},
        "/v1/relationships": {"engine", "input", "planet_relationship"},
        # `source` and `authority` are the provenance stamp carried by every
        # block that encodes a rule; see astro_engine/provenance.py.
        "/v1/kp": {"engine", "input", "houses", "planets", "house_significators",
                   "source", "authority"},
    }
    for path, keys in expected_keys.items():
        actual = set(route_bodies[path])
        check(f"{path} response keys", actual == keys,
              f"missing={sorted(keys - actual)} unexpected={sorted(actual - keys)}")

    # Cross-route identity checks for blocks that are also returned by /v1/chart.
    check("ashtakavarga route matches chart", route_bodies["/v1/ashtakavarga"].get("ashtakavarga") == chart.get("ashtakavarga"), "block differs")
    check("sudarsana route matches chart", route_bodies["/v1/sudarshana"].get("sudarshana_chakra") == chart.get("sudarshana_chakra"), "block differs")
    check("upagraha route matches chart", route_bodies["/v1/upagrahas"].get("upagrahas") == chart.get("upagrahas"), "block differs")
    check("relationship route matches chart", route_bodies["/v1/relationships"].get("planet_relationship") == chart.get("planet_relationship"), "block differs")
    check("dosha route matches chart", route_bodies["/v1/doshas"].get("doshas", {}).get("kaal_sarpa") == chart.get("doshas", {}).get("kaal_sarpa"), "block differs")

    # Every optional switch is exercised alone as well as in the full request.
    flag_to_keys = {
        "include_yogas": {"yogas"},
        "include_transits": {"transits", "transits_source"},
        "include_ashtakavarga": {"ashtakavarga", "ashtakavarga_source",
                                 "sarvashtakavarga"},
        "include_upagrahas": {"upagrahas"},
        "include_relationships": {"planet_relationship"},
        "include_doshas": {"doshas"},
        "include_calendar": {"solstice", "drik_ritu", "sudarshana_chakra"},
        "include_nakshatra_info": {"nakshatra_info"},
    }
    minimal = {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139, "longitude": 77.2090}
    # Unconditional chart keys. `rashi_aspects` and `sources` are always
    # present and are not gated behind any include_ flag.
    base_keys = {"engine", "input", "lagna", "midheaven", "cusps", "grahas", "houses", "aspects", "rashi_aspects", "sources", "panchanga", "solar_day", "vargas", "dasha", "current_dasha"}
    for flag, expected in flag_to_keys.items():
        status, body, _ = call("POST", "/v1/chart", {**minimal, flag: True})
        body = good(status, f"isolated flag {flag}", body)
        check(f"isolated flag keys {flag}", expected <= set(body), f"got={sorted(body)}")
        check(f"isolated flag no unrelated extras {flag}", (set(body) - base_keys - expected) == set(), f"extras={sorted(set(body)-base_keys-expected)}")


def test_chart_matrix():
    # Independent places and date regimes, including DST, leap day, southern
    # hemisphere seasons, and a high-latitude summer case.
    cases = [
        ("Delhi", "1990-01-15", "04:30", 28.6139, 77.2090, "Asia/Kolkata"),
        ("Mumbai", "1975-08-22", "17:45", 19.0760, 72.8777, "Asia/Kolkata"),
        ("Chennai", "2003-03-07", "09:05", 13.0827, 80.2707, "Asia/Kolkata"),
        ("London", "1988-11-02", "23:20", 51.5074, -0.1278, "Europe/London"),
        ("New York leap day", "2000-02-29", "00:01:59", 40.7128, -74.0060, "America/New_York"),
        ("Sydney", "1985-07-15", "12:00", -33.8688, 151.2093, "Australia/Sydney"),
        ("Singapore", "2020-06-21", "12:00", 1.3521, 103.8198, "Asia/Singapore"),
        ("Tromso summer", "2020-06-21", "12:00", 69.6492, 18.9553, "Europe/Oslo"),
    ]
    for label, day, clock, lat, lon, tz in cases:
        payload = {
            "date": day, "time": clock, "latitude": lat, "longitude": lon,
            "timezone": tz, "reference_time": "2026-09-20T12:00:00",
            "vargas": ["D1", "D9", "D10", "D60"],
            "include_yogas": True, "include_transits": True,
            "include_ashtakavarga": True, "include_upagrahas": True,
            "include_relationships": True, "include_doshas": True,
            "include_calendar": True, "include_nakshatra_info": True,
        }
        status, body, _ = call("POST", "/v1/chart", payload)
        # The high-latitude case may legitimately lack a sunrise in some
        # seasons; even then it must be a controlled 422, never a 500.
        check(f"chart matrix {label} controlled response", status in (200, 422), f"HTTP {status}: {body}")
        if status == 200:
            test_chart_invariants(body, expected_vargas={"D1", "D9", "D10", "D60"})
            test_varga_math(body)
            test_deep_blocks(body)
            check(f"chart matrix {label} input coords", body.get("input", {}).get("latitude") == lat, repr(body.get("input")))

    for compatible in (False, True):
        payload = {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139, "longitude": 77.2090, "prokerala_compatible": compatible}
        status, body, _ = call("POST", "/v1/chart", payload)
        body = good(status, f"compatibility mode {compatible}", body)
        check(f"compatibility dasha precision {compatible}", body.get("dasha", {}).get("traversed_precision") == (3 if compatible else None), repr(body.get("dasha")))


def test_high_latitude_route_safety():
    # Swiss Ephemeris has no ordinary sunrise/sunset event during polar day or
    # polar night. Every affected route should return a controlled 422 or a
    # documented polar-day representation, never an unhandled HTTP 500.
    cases = [
        ("Tromso polar day", "2020-06-21", 69.6492, 18.9553, "Europe/Oslo"),
        ("Tromso polar night", "2020-12-21", 69.6492, 18.9553, "Europe/Oslo"),
        ("Longyearbyen polar day", "2020-06-21", 78.2232, 15.6469, "Arctic/Longyearbyen"),
        ("Longyearbyen polar night", "2020-12-21", 78.2232, 15.6469, "Arctic/Longyearbyen"),
    ]
    chart_routes = (
        "/v1/chart", "/v1/chart/summary", "/v1/yogas", "/v1/transits",
        "/v1/ashtakavarga", "/v1/upagrahas", "/v1/doshas", "/v1/nakshatra",
        "/v1/sudarshana", "/v1/relationships", "/v1/kp",
    )
    for label, day, lat, lon, tz in cases:
        payload = {"date": day, "time": "12:00", "latitude": lat, "longitude": lon, "timezone": tz}
        for path in chart_routes:
            status, body, _ = call("POST", path, payload)
            check(f"{label} {path} safe failure", status in (200, 422), f"HTTP {status}: {body}")
        for path, body in (
            ("/v1/muhurta", {"date": day, "latitude": lat, "longitude": lon, "timezone": tz}),
            ("/v1/bala", {"date": day, "latitude": lat, "longitude": lon, "timezone": tz}),
        ):
            status, result, _ = call("POST", path, body)
            check(f"{label} {path} safe failure", status in (200, 422), f"HTTP {status}: {result}")


def test_special_routes():
    boy = {"date": "1990-01-15", "time": "04:30", "place": "Delhi", "timezone": "Asia/Kolkata"}
    girl = {"date": "1992-06-20", "time": "14:15", "place": "Mumbai", "timezone": "Asia/Kolkata"}
    status, body, _ = call("POST", "/v1/matching", {"boy": boy, "girl": girl})
    body = good(status, "POST /v1/matching", body)
    check("matching total range", 0 <= body.get("guna_milan", {}).get("total_points", -1) <= 36, repr(body))
    check("matching koot list", len(body.get("guna_milan", {}).get("guna", [])) == 8, repr(body))
    check("matching nadi block", "nadi_dosha" in body, repr(body))

    for twelve in (False, True):
        status, body, _ = call("POST", "/v1/porutham", {
            "boy_nakshatra": 9, "boy_nakshatra_pada": 1,
            "girl_nakshatra": 12, "girl_nakshatra_pada": 2,
            "twelve": twelve,
        })
        body = good(status, f"POST /v1/porutham twelve={twelve}", body)
        check(f"porutham matches list twelve={twelve}", len(body.get("matches", [])) in (10, 12), repr(body))
        check(f"porutham points bounded twelve={twelve}", 0 <= body.get("obtained_points", -1) <= body.get("maximum_points", -1), repr(body))

    for b_star, b_pada, g_star, g_pada in ((0, 1, 0, 1), (0, 4, 26, 4), (26, 1, 0, 4), (26, 4, 26, 1)):
        status, body, _ = call("POST", "/v1/porutham", {
            "boy_nakshatra": b_star, "boy_nakshatra_pada": b_pada,
            "girl_nakshatra": g_star, "girl_nakshatra_pada": g_pada,
            "twelve": True,
        })
        body = good(status, f"porutham boundary {b_star}/{b_pada}-{g_star}/{g_pada}", body)
        check("porutham boundary matches", len(body.get("matches", [])) == 12, repr(body))

    for extra in ({}, {"janma_nakshatra": 10, "janma_rasi": 4}):
        status, body, _ = call("POST", "/v1/bala", {"date": "2026-09-20", "place": "Delhi", "timezone": "Asia/Kolkata", **extra})
        body = good(status, f"POST /v1/bala personal={bool(extra)}", body)
        check(f"bala tara block personal={bool(extra)}", "tara_bala" in body, repr(body))
        if extra:
            check("bala personal block", "for_person" in body, repr(body))

    for name in (("John", "", "Doe"), ("A", "B", "C"), ("Yvonne", "", "Wright")):
        for vowel in (False, True):
            status, body, _ = call("POST", "/v1/numerology", {
                "first_name": name[0], "middle_name": name[1], "last_name": name[2],
                "date_of_birth": "2004-02-12", "reference_date": "2026-09-20",
                "additional_vowel": vowel, "prokerala_compatible": vowel,
            })
            body = good(status, f"numerology {name} vowel={vowel}", body)
            check(f"numerology name chart {name} vowel={vowel}", "name_chart" in body, repr(body))

    for query in (
        {"q": "Delhi", "limit": 3},
        {"q": "London", "limit": 5, "country": "United Kingdom"},
        {"q": "Mumbai", "limit": 1, "country": "India"},
    ):
        status, body, _ = call("GET", "/v1/places", query=query)
        body = good(status, f"places {query}", body)
        check(f"places count {query}", body.get("count") == len(body.get("results", [])), repr(body))
        check(f"places limit {query}", len(body.get("results", [])) <= query["limit"], repr(body))
    for lat, lon in ((28.6139, 77.2090), (51.5074, -0.1278), (-33.8688, 151.2093), (0, 0)):
        status, body, _ = call("GET", "/v1/timezone", query={"latitude": lat, "longitude": lon})
        body = good(status, f"timezone {lat},{lon}", body)
        check(f"timezone string {lat},{lon}", isinstance(body.get("timezone"), str) and "/" in body.get("timezone", ""), repr(body))


def test_upagraha_and_ashtakavarga_invariants(chart):
    up = chart.get("upagrahas", [])
    names = [x.get("name") for x in up]
    check("eleven upagrahas", len(up) == 11, repr(up))
    check("upagraha names unique", len(set(names)) == len(names), repr(names))
    for item in up:
        check(f"upagraha longitude {item.get('name')}", 0 <= item.get("longitude", -1) < 360, repr(item))
    av = chart.get("ashtakavarga", {})
    check("seven BAV subjects", set(av) == {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"}, repr(av))
    for name, table in av.items():
        check(f"{name} BAV 12 signs", len(table.get("by_sign", [])) == 12, repr(table))
        check(f"{name} BAV total sum", sum(table.get("by_sign", [])) == table.get("total"), repr(table))
    sav = chart.get("sarvashtakavarga", {})
    check("SAV 12 signs", len(sav.get("by_sign", [])) == 12, repr(sav))
    check("SAV total sum", sum(sav.get("by_sign", [])) == sav.get("total"), repr(sav))


def test_validation_and_tool_contract():
    valid = {"date": "1990-01-15", "time": "04:30", "place": "Delhi"}
    invalids = [
        ("missing location", {"date": "1990-01-15", "time": "04:30"}),
        ("bad ayanamsa", {**valid, "ayanamsa": "bogus"}),
        ("bad varga", {**valid, "vargas": ["D999"]}),
        ("bad latitude", {**valid, "place": None, "latitude": 91, "longitude": 77}),
        ("bad node type", {**valid, "node_type": "meanish"}),
        ("bad dasha depth", {**valid, "dasha_depth": 0}),
        ("bad date", {**valid, "date": "not-a-date"}),
        ("bad time", {**valid, "time": "25:99"}),
        ("impossible date", {**valid, "date": "2023-02-30"}),
        ("unknown place", {"date": "1990-01-15", "time": "04:30", "place": "Not A Real Place"}),
        ("bad timezone", {**valid, "timezone": "Not/A_Timezone"}),
    ]
    for label, payload in invalids:
        status, body, _ = call("POST", "/v1/chart", payload)
        check(f"chart rejects {label}", status == 422, f"HTTP {status}: {body}")
    status, body, _ = call("POST", "/v1/muhurta", {"date": "2026-09-20"})
    check("muhurta rejects missing location", status == 422, f"HTTP {status}: {body}")
    status, body, _ = call("POST", "/v1/porutham", {
        "boy_nakshatra": 0, "boy_nakshatra_pada": 0,
        "girl_nakshatra": 26, "girl_nakshatra_pada": 5,
    })
    check("porutham rejects invalid padas", status == 422, f"HTTP {status}: {body}")
    status, body, _ = call("POST", "/v1/matching", {"boy": {"date": "1990-01-15", "time": "04:30"}, "girl": {"date": "1992-06-20", "time": "14:15"}})
    check("matching rejects missing nested locations", status == 422, f"HTTP {status}: {body}")

    status, definition, _ = call("GET", "/v1/tool-definition")
    definition = good(status, "tool-definition", definition)
    required = set(definition.get("input_schema", {}).get("required", []))
    check("tool chart requires date/time", required == {"date", "time"}, repr(required))
    # This should fail at the endpoint despite being valid under the advertised schema.
    status, body, _ = call("POST", "/v1/chart", {"date": "1990-01-15", "time": "04:30"})
    check("tool schema exposes location contract defect", status == 422, f"HTTP {status}: {body}")
    status, definitions, _ = call("GET", "/v1/tool-definitions")
    definitions = good(status, "tool-definitions", definitions)
    check("four tool definitions", len(definitions) == 4, repr(definitions))
    names = {item.get("name") for item in definitions}
    check("tool definition names", names == {"get_vedic_chart", "get_kundli_matching", "get_muhurta", "get_kp_chart"}, repr(names))


def test_http_methods():
    for path in ("/v1/chart", "/v1/yogas", "/v1/muhurta", "/v1/matching"):
        status, body, _ = call("GET", path)
        check(f"GET {path} rejected", status == 405, f"HTTP {status}: {body}")
    status, body, _ = call("GET", "/")
    check("GET / returns 404", status == 404, f"HTTP {status}: {body}")


def main() -> int:
    test_health_and_openapi()
    test_chart_routes()
    # Recover a chart for cross-field invariant tests.
    status, chart, _ = call("POST", "/v1/chart", chart_payload())
    if status == 200:
        test_upagraha_and_ashtakavarga_invariants(chart)
        test_deep_blocks(chart)
        test_varga_math(chart)
    else:
        check("recovery chart", False, f"HTTP {status}: {chart}")
    test_special_routes()
    test_chart_matrix()
    test_high_latitude_route_safety()
    test_validation_and_tool_contract()
    test_http_methods()
    print(f"{passed}/{checks} independent checks pass across {requests_made} HTTP requests")
    if failures:
        print(f"{len(failures)} failures:")
        for failure in failures[:120]:
            print(f"  - {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
