"""Compare the engine against the responses `sweep_coverage.py` cached.

Reads the cache only; spends no credits. For each endpoint it prints how many
births agree and the first differences, so a mismatch can be chased down.

    python validation/compare_coverage.py [endpoint ...]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, ".")
import warnings  # noqa: E402

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from astro_engine.api import app  # noqa: E402
from validation.parallel_fetch import cache_path  # noqa: E402
from validation.sweep_coverage import KP, births, jobs  # noqa: E402

client = TestClient(app)
ARCSEC = 1 / 3600


def request_for(params: dict, zone: str) -> dict:
    moment = datetime.fromisoformat(params["datetime"]).replace(tzinfo=None)
    lat, lon = (float(x) for x in params["coordinates"].split(","))
    return {
        "date": moment.strftime("%Y-%m-%d"), "time": moment.strftime("%H:%M:%S"),
        "latitude": lat, "longitude": lon, "timezone": zone,
        "ayanamsa": "krishnamurti" if params["ayanamsa"] == KP else "lahiri",
        "prokerala_compatible": True,
    }


def deep_diff(ours, theirs, path="", out=None, tol=1e-6):
    """Every leaf where `theirs` (Prokerala) differs from `ours`."""
    out = [] if out is None else out
    if isinstance(theirs, dict):
        if not isinstance(ours, dict):
            out.append(f"{path}: engine has {type(ours).__name__}")
            return out
        for key, value in theirs.items():
            if key not in ours:
                out.append(f"{path}.{key}: missing in engine")
            else:
                deep_diff(ours[key], value, f"{path}.{key}", out, tol)
    elif isinstance(theirs, list):
        if not isinstance(ours, list) or len(ours) != len(theirs):
            out.append(f"{path}: len engine={len(ours) if isinstance(ours, list) else ours!r} "
                       f"prokerala={len(theirs)}")
            return out
        for i, (a, b) in enumerate(zip(ours, theirs)):
            deep_diff(a, b, f"{path}[{i}]", out, tol)
    elif isinstance(theirs, float) and isinstance(ours, (int, float)):
        if abs(ours - theirs) > tol:
            out.append(f"{path}: engine={ours} prokerala={theirs}")
    elif ours != theirs:
        out.append(f"{path}: engine={ours!r} prokerala={theirs!r}")
    return out


def _chart(req: dict, **extra) -> dict:
    return client.post("/v1/chart", json={**req, **extra}).json()


# Each comparator returns a list of difference strings; empty means agreement.
def cmp_planet_position(theirs, req):
    chart = _chart(req, vargas=["D1"], dasha_depth=1)
    diffs = []
    for p in theirs["planet_position"]:
        name = p["name"]
        ours = chart["lagna"] if name == "Ascendant" else chart["grahas"].get(name)
        if ours is None:
            diffs.append(f"{name}: missing in engine")
            continue
        delta = (ours["longitude"] - p["longitude"]) * 3600
        if abs(delta) > 1.0:
            diffs.append(f"{name}: longitude off {delta:+.2f}\"")
        if ours["sign_index"] != p["rasi"]["id"]:
            diffs.append(f"{name}: rasi {ours['sign_index']} vs {p['rasi']['id']}")
        if name != "Ascendant" and bool(ours["retrograde"]) != bool(p["is_retrograde"]):
            diffs.append(f"{name}: retrograde {ours['retrograde']} vs {p['is_retrograde']}")
    return diffs


def cmp_kp_planet_position(theirs, req):
    ours = client.post("/v1/kp", json=req).json()
    diffs = []
    for i, (a, b) in enumerate(zip(ours["houses"], theirs["houses"])):
        a = {**a, **{k: {"name": a[k]} for k in ("nakshatra_lord", "sub_lord", "sub_sub_lord")
                     if isinstance(a.get(k), str)}}
        d = (a["start_cusp"]["longitude"] - b["start_cusp"]["longitude"]) * 3600
        if abs(d) > 2:
            diffs.append(f"house {i + 1} cusp off {d:+.1f}\"")
        for lord in ("nakshatra_lord", "sub_lord", "sub_sub_lord"):
            if a[lord]["name"] != b[lord]["name"]:
                diffs.append(f"house {i + 1} {lord} {a[lord]['name']} vs {b[lord]['name']}")
    by_name = {p["planet"]["name"]: p for p in ours["planets"]}
    for b in theirs["planet_positions"]:
        a = by_name.get(b["planet"]["name"])
        if a is None:
            diffs.append(f"{b['planet']['name']}: missing")
            continue
        for lord in ("nakshatra_lord", "sub_lord", "sub_sub_lord"):
            theirs_lord = b[lord]["name"]
            ours_lord = a[lord] if isinstance(a[lord], str) else a[lord]["name"]
            if ours_lord != theirs_lord:
                diffs.append(f"{b['planet']['name']} {lord} {ours_lord} vs {theirs_lord}")
        if a["house"] != b["house"]["number"]:
            diffs.append(f"{b['planet']['name']} house {a['house']} vs {b['house']['number']}")
        d = (a["longitude"] - b["longitude"]) * 3600
        if abs(d) > 1:
            diffs.append(f"{b['planet']['name']} longitude off {d:+.2f}\"")
    return diffs


def _names(items):
    return sorted(x["name"] for x in items)


def cmp_kp_house_significator(theirs, req):
    ours = client.post("/v1/kp", json=req).json()["house_significators"]
    diffs = []
    for a, b in zip(ours, theirs["house_significators"]):
        n = b["house"]["number"]
        for key in ("cusp_occupants", "cusp_nakshatra_occupants",
                    "cusp_owner_nakshatra_planets"):
            if _names(a.get(key, [])) != _names(b[key]):
                diffs.append(f"house {n} {key}: {_names(a.get(key, []))} vs {_names(b[key])}")
        if a["cusp_owner"]["name"] != b["cusp_owner"]["name"]:
            diffs.append(f"house {n} owner {a['cusp_owner']['name']} vs {b['cusp_owner']['name']}")
    return diffs


def cmp_kp_planet_significator(theirs, req):
    ours = client.post("/v1/kp", json=req).json()
    if "planet_significators" not in ours:
        return ["planet_significators: not implemented in engine"]
    return deep_diff(ours["planet_significators"], theirs["planet_significators"])


def cmp_dasha_periods(theirs, req):
    chart = _chart(req, vargas=["D1"], dasha_depth=3)
    diffs = []

    def walk(ours_list, theirs_list, keys, path):
        for a, b in zip(ours_list, theirs_list):
            if a["lord"] != b["name"]:
                diffs.append(f"{path}{b['name']}: lord {a['lord']}")
                return
            for edge in ("start", "end"):
                ta = datetime.fromisoformat(b[edge]).replace(tzinfo=None)
                oa = datetime.fromisoformat(a[edge])
                if ta != oa:
                    diffs.append(f"{path}{b['name']} {edge}: {a[edge]} vs {b[edge]}")
            if keys:
                walk(a.get("sub_periods", []), b.get(keys[0], []), keys[1:],
                     f"{path}{b['name']}/")

    walk(chart["dasha"]["mahadashas"], theirs["dasha_periods"],
         ["antardasha", "pratyantardasha"], "")
    return diffs


def cmp_planet_relationship(theirs, req):
    chart = _chart(req, vargas=["D1"], include_relationships=True)
    return deep_diff(chart["planet_relationship"], theirs["planet_relationship"])


def cmp_sarvashtakavarga(theirs, req):
    ours = _chart(req, vargas=["D1"], include_ashtakavarga=True)["sarvashtakavarga"]
    diffs = []
    for stage, block in theirs["sarvashtakavarga"].items():
        mine = ours.get(stage)
        if mine is None:
            diffs.append(f"{stage}: missing in engine")
            continue
        if mine.get("score") != block.get("score"):
            diffs.append(f"{stage} score {mine.get('score')} vs {block.get('score')}")
        for i, (a, b) in enumerate(zip(mine["houses"], block["houses"])):
            sa = {k: v for k, v in a.items() if k not in ("house", "rasi")}
            sb = {k: v for k, v in b.items() if k not in ("house", "rasi")}
            diffs += deep_diff(sa, sb, f"{stage}[{i}]")
            if a["rasi"].get("index", a["rasi"].get("id")) != b["rasi"]["id"]:
                diffs.append(f"{stage}[{i}] rasi {a['rasi']} vs {b['rasi']['id']}")
    return diffs


def cmp_mangal_dosha(theirs, req):
    d = client.post("/v1/doshas", json=req).json()["doshas"]["mangal_dosha"]
    diffs = []
    if d["has_yoga"] != theirs["has_dosha"]:
        diffs.append(f"has_dosha engine={d['has_yoga']} prokerala={theirs['has_dosha']} "
                     f"({theirs.get('description', '')[:80]})")
    return diffs


def cmp_kundli(theirs, req):
    chart = _chart(req, vargas=["D1"], include_yogas=True, include_nakshatra_info=True,
                   dasha_depth=1)
    diffs = []
    moon, sun = chart["grahas"]["Moon"], chart["grahas"]["Sun"]
    nd = theirs["nakshatra_details"]
    if moon["nakshatra_index"] != nd["nakshatra"]["id"]:
        diffs.append(f"nakshatra {moon['nakshatra_index']} vs {nd['nakshatra']['id']}")
    if moon["nakshatra_pada"] != nd["nakshatra"]["pada"]:
        diffs.append(f"pada {moon['nakshatra_pada']} vs {nd['nakshatra']['pada']}")
    if moon["sign_index"] != nd["chandra_rasi"]["id"]:
        diffs.append(f"chandra rasi {moon['sign_index']} vs {nd['chandra_rasi']['id']}")
    if sun["sign_index"] != nd["soorya_rasi"]["id"]:
        diffs.append(f"soorya rasi {sun['sign_index']} vs {nd['soorya_rasi']['id']}")
    flat = chart.get("nakshatra_info") or {}
    for key, value in nd.get("additional_info", {}).items():
        if key in flat and flat[key] != value:
            diffs.append(f"additional_info.{key}: {flat[key]!r} vs {value!r}")
        elif key not in flat:
            diffs.append(f"additional_info.{key}: missing in engine")
    md = theirs.get("mangal_dosha", {})
    ours_md = client.post("/v1/doshas", json=req).json()["doshas"]["mangal_dosha"]
    if md and ours_md["has_yoga"] != md["has_dosha"]:
        diffs.append(f"mangal_dosha {ours_md['has_yoga']} vs {md['has_dosha']}")
    ours_yogas = {y["name"]: y["has_yoga"]
                  for g in chart["yogas"]["yoga_details"] for y in g["yoga_list"]}
    for group in theirs.get("yoga_details", []):
        for y in group.get("yoga_list", []):
            if y["name"] not in ours_yogas:
                diffs.append(f"yoga {y['name']}: missing in engine")
            elif ours_yogas[y["name"]] != y["has_yoga"]:
                diffs.append(f"yoga {y['name']}: {ours_yogas[y['name']]} vs {y['has_yoga']}")
    return diffs


def cmp_papasamyam_check(theirs, pair):
    diffs = []
    for side in ("girl", "boy"):
        req = _pair_request(pair, side)
        ours = _chart(req, vargas=["D1"], include_doshas=True)["doshas"]["papasamyam"]
        diffs += deep_diff(ours, theirs[f"{side}_papasamyam"], side)
    return diffs


def cmp_porutham(theirs, pair):
    nak = {}
    for side in ("girl", "boy"):
        moon = _chart(_pair_request(pair, side), vargas=["D1"])["grahas"]["Moon"]
        nak[side] = (moon["nakshatra_index"], moon["nakshatra_pada"])
        info = theirs[f"{side}_info"]["nakshatra"]
        if (info["id"], info["pada"]) != nak[side]:
            return [f"{side} nakshatra {nak[side]} vs {(info['id'], info['pada'])}"]
    if pair["system"] != "tamil":
        return ["kerala system: not implemented in engine"]
    ours = client.post("/v1/porutham", json={
        "boy_nakshatra": nak["boy"][0], "boy_nakshatra_pada": nak["boy"][1],
        "girl_nakshatra": nak["girl"][0], "girl_nakshatra_pada": nak["girl"][1],
    }).json()
    ours_by_name = {m["name"]: m["has_porutham"] for m in ours.get("matches", [])}
    diffs = []
    for m in theirs["matches"]:
        if m["name"] not in ours_by_name:
            diffs.append(f"{m['name']}: missing in engine")
        elif ours_by_name[m["name"]] != m["has_porutham"]:
            diffs.append(f"{m['name']}: {ours_by_name[m['name']]} vs {m['has_porutham']}")
    return diffs


def _pair_request(pair, side):
    zone = _ZONE_BY_COORD[pair[f"{side}_coordinates"]]
    return request_for({"datetime": pair[f"{side}_dob"],
                        "coordinates": pair[f"{side}_coordinates"],
                        "ayanamsa": pair["ayanamsa"]}, zone)


def _close(ours: str, theirs: str, seconds: float) -> bool:
    a = datetime.fromisoformat(ours)
    b = datetime.fromisoformat(theirs).replace(tzinfo=None)
    return abs((a - b).total_seconds()) <= seconds


# Prokerala's Moon timings in the day endpoints scatter by about a second
# around ours (see README, Precision notes), so windows get two seconds.
WINDOW_SECONDS = 2.0


def _muhurta(req):
    return client.post("/v1/muhurta", json={
        "date": req["date"], "latitude": req["latitude"],
        "longitude": req["longitude"], "timezone": req["timezone"]}).json()


def cmp_anandadi_yoga(theirs, req):
    ours = _muhurta(req)["anandadi_yoga"]
    theirs = theirs["anandadi_yoga"]
    if len(ours) != len(theirs):
        return [f"count {len(ours)} vs {len(theirs)}: "
                f"{[o['id'] for o in ours]} vs {[t['id'] for t in theirs]}"]
    diffs = []
    for o, t in zip(ours, theirs):
        if o["id"] != t["id"]:
            diffs.append(f"id {o['id']} vs {t['id']}")
            continue
        if o["label_parity"] == "verified":
            for key in ("name", "type", "description"):
                if o[key] != t[key]:
                    diffs.append(f"{t['id']} {key} {o[key]!r} vs {t[key]!r}")
        for edge in ("start", "end"):
            if not _close(o[edge], t[edge], WINDOW_SECONDS):
                diffs.append(f"{t['name']} {edge} {o[edge]} vs {t[edge]}")
    return diffs


def cmp_not_implemented(name):
    return lambda theirs, req: [f"{name}: not implemented in engine"]


COMPARATORS = {
    "planet-position": cmp_planet_position,
    "kp-planet-position": cmp_kp_planet_position,
    "kp-house-significator": cmp_kp_house_significator,
    "kp-planet-significator": cmp_kp_planet_significator,
    "dasha-periods": cmp_dasha_periods,
    "planet-relationship": cmp_planet_relationship,
    "sarvashtakavarga": cmp_sarvashtakavarga,
    "mangal-dosha": cmp_mangal_dosha,
    "kundli": cmp_kundli,
    "papasamyam-check": cmp_papasamyam_check,
    "porutham": cmp_porutham,
    "anandadi-yoga": cmp_anandadi_yoga,
    "auspicious-yoga": cmp_not_implemented("auspicious yoga"),
    "chandrashtama-periods": cmp_not_implemented("yearly chandrashtama timings"),
}

_ZONE_BY_COORD = {f"{lat},{lon}": zone for _, _, lat, lon, zone in births()}


def main() -> int:
    only = set(sys.argv[1:])
    tally = defaultdict(lambda: [0, 0])
    details = defaultdict(list)
    for endpoint, params in jobs():
        if only and endpoint not in only or endpoint not in COMPARATORS:
            continue
        path = cache_path(endpoint, params)
        if not path.exists():
            continue
        theirs = json.loads(path.read_text(encoding="utf-8"))["data"]
        label = endpoint + (f" ({params['system']})" if "system" in params else "")
        if "coordinates" in params:
            req = request_for(params, _ZONE_BY_COORD[params["coordinates"]])
            when = params["datetime"]
        else:
            req, when = params, f"{params['girl_dob']} + {params['boy_dob']}"
        try:
            diffs = COMPARATORS[endpoint](theirs, req)
        except Exception as exc:  # noqa: BLE001
            diffs = [f"comparator crashed: {type(exc).__name__}: {exc}"]
        tally[label][1] += 1
        if diffs:
            details[label].append((when, diffs))
        else:
            tally[label][0] += 1
    for label, (ok, total) in sorted(tally.items()):
        print(f"{label:30s} {ok}/{total} agree")
        for when, diffs in details[label][:3]:
            print(f"    {when}: {len(diffs)} diffs")
            for d in diffs[:6]:
                print(f"      {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
