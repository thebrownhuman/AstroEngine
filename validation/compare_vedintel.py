"""Compare the engine with VedIntel, the second reference. Cache only.

VedIntel subtracts the nutation-included ayanamsa, as plain Swiss Ephemeris
does; the engine follows Prokerala and subtracts the nutation-free one. That
moves every longitude by the same 10-17 arcseconds, so longitudes are
compared after removing each chart's median offset, and everything discrete
-- sign, nakshatra, pada, lords, bindus, verdicts -- is compared exactly.

    python validation/compare_vedintel.py
"""

from __future__ import annotations

import json
import statistics
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from astro_engine.api import app  # noqa: E402
from validation.sweep_coverage import births  # noqa: E402
from validation.sweep_vedintel import PER_BIRTH, birth_params, pair_params, pairs  # noqa: E402
from validation.vedintel import cache_path  # noqa: E402

client = TestClient(app)
ABBR = {"As": "Lagna", "Su": "Sun", "Mo": "Moon", "Ma": "Mars", "Me": "Mercury",
        "Ju": "Jupiter", "Ve": "Venus", "Sa": "Saturn", "Ra": "Rahu", "Ke": "Ketu"}
SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
            "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
POSITION_TOLERANCE_ARCSEC = 1.0
# Their yoga names -> ours, for the yogas both sides compute.
YOGA_NAMES = {
    "Gaja Kesari Yoga": "Gajakesari Yoga", "Sunapha Yoga": "Sunapha Yoga",
    "Anapha Yoga": "Anapha Yoga", "Durudhara Yoga": "Duradhara Yoga",
    "Kahala Yoga": "Kahala Yoga", "Ubhayachari Yoga": "Ubhaya Chari Yoga",
    "Ruchaka Yoga (Pancha Mahapurusha)": "Ruchaka Yoga",
    "Bhadra Yoga (Pancha Mahapurusha)": "Bhadra Yoga",
    "Hamsa Yoga (Pancha Mahapurusha)": "Hamsa Yoga",
    "Malavya Yoga (Pancha Mahapurusha)": "Malavya Yoga",
    "Sasa Yoga (Pancha Mahapurusha)": "Sasa Yoga",
    "Shasha Yoga (Pancha Mahapurusha)": "Sasa Yoga",
}


def _nak_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("shirsha", "shira").replace("shtha", "shta") \
        .replace("aa", "a").replace("moola", "mula")


def request(moment, lat, lon, zone, **extra) -> dict:
    return {"date": moment.strftime("%Y-%m-%d"), "time": moment.strftime("%H:%M"),
            "latitude": lat, "longitude": lon, "timezone": zone, **extra}


def _bodies(response: dict) -> dict:
    return {ABBR[v["name"]]: v for v in response.values()
            if isinstance(v, dict) and v.get("name") in ABBR}


def cmp_planets(theirs, chart):
    bodies = _bodies(theirs)
    ours = {**chart["grahas"], "Lagna": chart["lagna"]}
    offset = statistics.median((ours[n]["longitude"] - b["global_degree"] + 180) % 360 - 180
                               for n, b in bodies.items())
    diffs = []
    for name, b in bodies.items():
        o = ours[name]
        residual = ((o["longitude"] - b["global_degree"] + 180) % 360 - 180 - offset) * 3600
        if abs(residual) > POSITION_TOLERANCE_ARCSEC:
            diffs.append(f"{name} longitude residual {residual:+.2f}\"")
        if o["sign_index"] + 1 != b["rasi_no"]:
            diffs.append(f"{name} sign {o['sign_index'] + 1} vs {b['rasi_no']}")
        if _nak_name(o["nakshatra"]) != _nak_name(b["nakshatra"]):
            diffs.append(f"{name} nakshatra {o['nakshatra']} vs {b['nakshatra']}")
        if o["nakshatra_pada"] != b["nakshatra_pada"]:
            diffs.append(f"{name} pada {o['nakshatra_pada']} vs {b['nakshatra_pada']}")
        if name not in ("Lagna", "Rahu", "Ketu") and bool(o["retrograde"]) != bool(b["retro"]):
            diffs.append(f"{name} retro {o['retrograde']} vs {b['retro']}")
        if name != "Lagna" and o["house"] != b["house"]:
            diffs.append(f"{name} house {o['house']} vs {b['house']}")
    return diffs, offset * 3600


def cmp_navamsa(theirs, chart):
    d9 = chart["vargas"]["D9"]
    diffs = []
    for name, b in _bodies(theirs).items():
        sign = (d9["lagna"] if name == "Lagna" else d9["grahas"][name]["sign"])["index"]
        if sign + 1 != b["rasi_no"]:
            diffs.append(f"D9 {name} {sign + 1} vs {b['rasi_no']}")
    return diffs


def cmp_ashtakavarga(theirs, chart):
    order = theirs["ashtakvarga_order"]
    diffs = []
    for name, row in zip(order, theirs["ashtakvarga_points"]):
        if name not in chart["ashtakavarga"]:
            continue
        mine = chart["ashtakavarga"][name]["by_sign"]
        if mine != row:
            diffs.append(f"{name} {mine} vs {row}")
    sarva = [x["bindus"] for x in sorted(theirs["sarvashtakvarga"], key=lambda x: x["sign_no"])]
    if chart["sarvashtakavarga"]["by_sign"] != sarva:
        diffs.append(f"sarva {chart['sarvashtakavarga']['by_sign']} vs {sarva}")
    return diffs


def cmp_kp_houses(theirs, kp):
    diffs = []
    for a, b in zip(kp["houses"], theirs):
        n = b["house"]
        if SIGNS_EN[a["rasi"]["index"]] != b["sign"]:
            diffs.append(f"cusp {n} sign {SIGNS_EN[a['rasi']['index']]} vs {b['sign']}")
        if a["nakshatra_lord"] != b["nakshatra_lord"]:
            diffs.append(f"cusp {n} star lord {a['nakshatra_lord']} vs {b['nakshatra_lord']}")
        if a["sub_lord"] != b["sub_lord"]:
            diffs.append(f"cusp {n} sub lord {a['sub_lord']} vs {b['sub_lord']} "
                         f"(ours {a['start_cusp']['longitude']:.4f}, theirs {b['cusp_degree']})")
    return diffs


def cmp_kp_planets(theirs, kp):
    ours = {p["planet"]["name"]: p for p in kp["planets"]}
    diffs = []
    for b in theirs:
        a = ours.get(b["planet"])
        if a is None:
            continue
        for key in ("nakshatra_lord", "sub_lord"):
            if a[key] != b[key]:
                diffs.append(f"{b['planet']} {key} {a[key]} vs {b[key]} "
                             f"(ours {a['longitude']:.4f}, theirs {b['degree']})")
        if a["house"] != b["house"]:
            diffs.append(f"{b['planet']} KP house {a['house']} vs {b['house']}")
    return diffs


def _rel(label: str) -> str:
    return label.split(" (")[0].replace("Great ", "Great_")


def cmp_friendship(theirs, chart):
    rel = chart["planet_relationship"]
    table = {}
    for kind in ("natural", "temporal", "compound"):
        for cell in rel[f"{kind}_relationship"]:
            table[(kind, cell["first_planet"]["name"], cell["second_planet"]["name"])] = cell["relationship"]
    ours_label = {"Friend": "Friend", "Enemy": "Enemy", "Neutral": "Neutral",
                  "Extreme Friend": "Great_Friend", "Extreme Enemy": "Great_Enemy"}
    diffs = []
    for row in theirs:
        for x in row["relationships"]:
            for kind, key in (("natural", "natural_relationship"),
                              ("temporal", "temporary_relationship"),
                              ("compound", "compound_relationship")):
                mine = table.get((kind, row["planet"], x["planet"]))
                if mine is None:
                    continue
                if ours_label.get(mine, mine) != _rel(x[key]):
                    diffs.append(f"{kind} {row['planet']}->{x['planet']}: {mine} vs {x[key]}")
    return diffs


def cmp_yogas(theirs, chart):
    ours = {y["name"]: y["has_yoga"] for g in chart["yogas"]["yoga_details"] for y in g["yoga_list"]}
    present = {YOGA_NAMES[y["name"]] for y in theirs if y["name"] in YOGA_NAMES}
    diffs = []
    for theirs_name, mine in sorted(set(YOGA_NAMES.items()), key=lambda kv: kv[1]):
        if mine not in ours:
            continue
        if ours[mine] != (mine in present):
            diffs.append(f"{mine}: engine {ours[mine]} vs vedintel {mine in present}")
    return sorted(set(diffs))


def _gmt(text: str) -> datetime:
    return datetime.strptime(text, "%a, %d %b %Y %H:%M:%S GMT")


def cmp_mahadasha(theirs, chart, utc_offset):
    ours = chart["dasha"]["mahadashas"]
    lords = [p["lord"] for p in ours]
    theirs_lords = [p["name"] for p in theirs]
    diffs = []
    if lords[:len(theirs_lords)] != theirs_lords[:len(lords)]:
        diffs.append(f"lord order {lords} vs {theirs_lords}")
    if diffs:
        return diffs, 0.0
    worst = 0.0
    # Their first entry starts at birth, ours at the cycle start; compare the
    # boundaries after it.
    for a, b in zip(ours[1:], theirs[1:]):
        start = datetime.fromisoformat(a["start"]) - timedelta(hours=utc_offset)
        worst = max(worst, abs((start - _gmt(b["start"])).total_seconds()) / 86400)
    return diffs, worst


def cmp_kaalsarp(theirs, chart):
    ks = chart["doshas"]["kaal_sarpa"]
    ours = bool(ks.get("has_dosha", ks.get("present")))
    return [] if ours == theirs["is_dosha_present"] else [
        f"kaal sarpa engine {ours} vs {theirs['is_dosha_present']}"]


def cmp_mangal(theirs, mangal):
    return [] if mangal["has_yoga"] == theirs["is_dosha_present_mars_from_lagna"] else [
        f"mangal from lagna engine {mangal['has_yoga']} vs {theirs['is_dosha_present_mars_from_lagna']}"
        f" ({mangal.get('reason', '')})"]


def main() -> int:
    tally = defaultdict(lambda: [0, 0])
    details = defaultdict(list)
    offsets, dasha_days = [], []
    for label, moment, lat, lon, zone in births():
        params = birth_params(moment, lat, lon, zone)
        cached = {}
        for endpoint, extra in PER_BIRTH:
            path = cache_path(endpoint, {**params, **extra})
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("status") == 200:
                    cached[endpoint] = payload["response"]
        if not cached:
            continue
        req = request(moment, lat, lon, zone)
        chart = client.post("/v1/chart", json={
            **req, "vargas": ["D1", "D9"], "include_ashtakavarga": True,
            "include_relationships": True, "include_yogas": True,
            "include_doshas": True}).json()
        kp = client.post("/v1/kp", json={**req, "ayanamsa": "krishnamurti"}).json()
        mangal = client.post("/v1/doshas", json=req).json()["doshas"]["mangal_dosha"]

        checks = {
            "horoscope/planet-details": lambda t: cmp_planets(t, chart),
            "horoscope/divisional-charts": lambda t: cmp_navamsa(t, chart),
            "horoscope/ashtakvarga": lambda t: cmp_ashtakavarga(t, chart),
            "extended-horoscope/kp-houses": lambda t: cmp_kp_houses(t, kp),
            "extended-horoscope/kp-planets": lambda t: cmp_kp_planets(t, kp),
            "extended-horoscope/friendship-table": lambda t: cmp_friendship(t, chart),
            "extended-horoscope/yoga-list": lambda t: cmp_yogas(t, chart),
            "dashas/mahadasha": lambda t: cmp_mahadasha(t, chart, params["tz"]),
            "dosha/kaalsarp-dosh": lambda t: cmp_kaalsarp(t, chart),
            "dosha/mangal-dosh": lambda t: cmp_mangal(t, mangal),
        }
        for endpoint, check in checks.items():
            if endpoint not in cached:
                continue
            try:
                result = check(cached[endpoint])
            except Exception as exc:  # noqa: BLE001
                result = [f"comparator crashed: {type(exc).__name__}: {exc}"]
            if endpoint == "horoscope/planet-details":
                result, off = result
                offsets.append(off)
            if endpoint == "dashas/mahadasha":
                result, worst = result
                dasha_days.append(worst)
            tally[endpoint][1] += 1
            if result:
                details[endpoint].append((label, result))
            else:
                tally[endpoint][0] += 1

    for boy, girl in pairs():
        path = cache_path("matching/north-match", pair_params(boy, girl))
        if not path.exists():
            continue
        theirs = json.loads(path.read_text(encoding="utf-8"))["response"]
        ours = client.post("/v1/matching", json={
            "boy": request(*boy[1:]), "girl": request(*girl[1:])}).json()["guna_milan"]
        points = {k["name"].replace("Vashya", "Vasya"): k["points"] for k in theirs["koots"]}
        diffs = [f"{g['name']} {g['obtained_points']} vs {points.get(g['name'])}"
                 for g in ours["guna"] if points.get(g["name"]) != g["obtained_points"]]
        tally["matching/north-match"][1] += 1
        if diffs:
            details["matching/north-match"].append((f"{boy[0]} + {girl[0]}", diffs))
        else:
            tally["matching/north-match"][0] += 1

    for endpoint, (ok, total) in sorted(tally.items()):
        print(f"{endpoint:40s} {ok}/{total} agree")
        for label, diffs in details[endpoint][:4]:
            print(f"    {label}: {'; '.join(diffs[:4])}")
    if offsets:
        print(f"equinox offset ours-theirs: {min(offsets):+.1f}\" to {max(offsets):+.1f}\"")
    if dasha_days:
        print(f"mahadasha start difference: up to {max(dasha_days):.2f} days")
    agree = sum(ok for ok, _ in tally.values())
    total = sum(n for _, n in tally.values())
    print(f"{agree}/{total} VedIntel checks pass across {len(tally)} endpoints")
    return 0 if agree == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
