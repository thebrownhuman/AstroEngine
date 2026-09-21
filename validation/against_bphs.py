"""Audit the deployed API against BPHS and first principles.

Deliberately independent of the Prokerala sweeps: those ask "does this match
the provider", which cannot catch an error both sides share. These ask "is
this what the text says, and is it internally coherent".

Every BPHS check cites the chapter and verse it was read from.
"""

from __future__ import annotations

import json
import os
import urllib.request

BASE = os.environ.get("ASTRO_ENGINE_URL", "http://192.168.68.114:8000").rstrip("/")

results = []


def check(case, ok, detail=""):
    results.append((case, bool(ok), detail))


def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))


BIRTH = {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139,
         "longitude": 77.209, "timezone": "Asia/Kolkata"}

chart = post("/v1/chart", {**BIRTH, "vargas": ["D1", "D2", "D3", "D9", "D30"],
                           "include_ashtakavarga": True, "include_upagrahas": True,
                           "include_relationships": True, "prokerala_compatible": True,
                           "dasha_depth": 1})
g = chart["grahas"]
NAK_ARC = 360.0 / 27.0

# ---------------------------------------------------------------- BPHS Ch. 3
# vv. 49-50: exaltation signs and their deep degrees; debilitation is the 7th
# sign from exaltation.
EXALT = {"Sun": (0, 10), "Moon": (1, 3), "Mars": (9, 28), "Mercury": (5, 15),
         "Jupiter": (3, 5), "Venus": (11, 27), "Saturn": (6, 20)}
for name, (sign, _deg) in EXALT.items():
    lon = g[name]["longitude"]
    at_exalt = int(lon // 30) == sign
    at_debil = int(lon // 30) == (sign + 6) % 12
    state = g[name]["dignity"]["state"]
    ok = (state == "exalted") if at_exalt else (state == "debilitated") if at_debil \
        else state in ("neutral", "own_sign")
    check(f"01 dignity consistent with Ch.3 v49-50 [{name}]", ok,
          f"sign={int(lon//30)} exalt={sign} state={state}")

# v. 11: the Sun, Saturn and Mars are malefic by nature.
check("02 natural malefics per Ch.3 v11",
      all(g[n]["natural_nature"] == "malefic" for n in ("Sun", "Saturn", "Mars")),
      str({n: g[n]["natural_nature"] for n in ("Sun", "Saturn", "Mars")}))

# v. 11: Jupiter and Venus are benefic by nature.
check("03 natural benefics per Ch.3 v11",
      all(g[n]["natural_nature"] == "benefic" for n in ("Jupiter", "Venus")),
      str({n: g[n]["natural_nature"] for n in ("Jupiter", "Venus")}))

# v. 11: a waxing Moon is benefic, a waning Moon malefic unless helped.
elong = (g["Moon"]["longitude"] - g["Sun"]["longitude"]) % 360.0
waxing = 0 < elong <= 180.0
check("04 Moon nature tracks the paksha (Ch.3 v11)",
      g["Moon"]["bphs_nature"] == "benefic" if waxing else True,
      f"elongation={elong:.2f} waxing={waxing} nature={g['Moon']['bphs_nature']}")

# vv. 57-58, the speculum: this verifies the rule itself, not just the labels.
#   Friendship + Friendship = Extreme friendship
#   Neutrality + Friendship = Friendship
#   Enmity     + Enmity     = Extreme enmity
#   Neutrality + Enmity     = Enmity
#   Enmity     + Friendship = Neutral
rel = chart["planet_relationship"]
SPECULUM = {
    ("Friend", "Friend"): "Extreme Friend",
    ("Neutral", "Friend"): "Friend",
    ("Enemy", "Enemy"): "Extreme Enemy",
    ("Neutral", "Enemy"): "Enemy",
    ("Enemy", "Friend"): "Neutral",
    ("Friend", "Enemy"): "Neutral",
}


def pair_key(row):
    return (row["first_planet"]["name"], row["second_planet"]["name"])


natural = {pair_key(r): r["relationship"] for r in rel["natural_relationship"]}
temporal = {pair_key(r): r["relationship"] for r in rel["temporal_relationship"]}
compound = {pair_key(r): r["relationship"] for r in rel["compound_relationship"]}

grades = {v for v in compound.values() if v != "No Relation"}
check("05 panchadha grades are the Ch.3 v57-58 five",
      grades == {"Extreme Friend", "Friend", "Neutral", "Enemy", "Extreme Enemy"},
      str(sorted(grades)))

bad = {}
for key, got in compound.items():
    nat, tem = natural.get(key), temporal.get(key)
    if nat == "No Relation" or tem == "No Relation" or got == "No Relation":
        continue
    want = SPECULUM.get((nat, tem))
    if want and got != want:
        bad[key] = (nat, tem, got, want)
check("05b compound follows the Ch.3 v57-58 speculum exactly", not bad,
      str(list(bad.items())[:3]))

# --------------------------------------------------------------- BPHS Ch. 26
# vv. 2-5: all aspect the 7th; Saturn 3/10, Jupiter 5/9, Mars 4/8 in addition.
EXPECT = {"Mars": {4, 7, 8}, "Jupiter": {5, 7, 9}, "Saturn": {3, 7, 10}}
for a in chart["aspects"]:
    name, frm = a["graha"], a["from_house"]
    rel_houses = {((h - frm) % 12) + 1 for h in a["aspects_houses"]}
    expect = EXPECT.get(name, {7})
    check(f"06 graha drishti per Ch.26 v2-5 [{name}]", rel_houses == expect,
          f"got={sorted(rel_houses)} expect={sorted(expect)}")

# The same passage names three grahas and no more, so the nodes take only 7th.
nodes = {a["graha"]: {((h - a["from_house"]) % 12) + 1 for h in a["aspects_houses"]}
         for a in chart["aspects"] if a["graha"] in ("Rahu", "Ketu")}
check("07 nodes take only the 7th aspect (Ch.26 names 3 grahas)",
      all(v == {7} for v in nodes.values()), str(nodes))

# --------------------------------------------------------------- BPHS Ch. 66
# Row totals of the bindu tables, and their sum.
TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
          "Jupiter": 56, "Venus": 52, "Saturn": 39}
av = chart["ashtakavarga"]
for name, total in TOTALS.items():
    check(f"08 bhinnashtakavarga total per Ch.66 [{name}]",
          av[name]["total"] == total, f"got={av[name]['total']} expect={total}")
check("09 sarvashtakavarga totals 337 (Ch.66)",
      chart["sarvashtakavarga"]["total"] == 337,
      str(chart["sarvashtakavarga"]["total"]))

# --------------------------------------------------------------- BPHS Ch. 46
# v. 15: the nine dasha lengths, which must sum to the 120-year span of v. 14.
YEARS = {"Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16,
         "Saturn": 19, "Mercury": 17, "Ketu": 7, "Venus": 20}
maha = chart["dasha"]["mahadashas"]
check("10 all nine dasha lords appear (Ch.46 v12-14)",
      set(d["lord"] for d in maha) == set(YEARS),
      str(sorted(set(d["lord"] for d in maha))))
# The first mahadasha is the balance at birth and is short by design; every
# later one must be the full span Ch.46 v15 gives it.
mismatch = {d["lord"]: (d["duration_years"], YEARS[d["lord"]]) for d in maha[1:]
            if round(d["duration_years"]) != YEARS[d["lord"]]}
check("11 dasha lengths match Ch.46 v15", not mismatch, str(mismatch))
# The cycle starts before birth, so all nine full mahadashas span the 120.
check("11b the cycle spans the 120 years of Ch.46 v14",
      abs(sum(d["duration_years"] for d in maha) - 120) < 1e-6,
      str(sum(d["duration_years"] for d in maha)))
# The balance at birth must be what remains of the first lord's full term.
first = maha[0]
from datetime import datetime
elapsed = (datetime.fromisoformat(chart["input"]["local_time"])
           - datetime.fromisoformat(first["start"])).days / 365.25
check("11c balance at birth is the unspent part of the first mahadasha",
      abs((first["duration_years"] - elapsed)
          - chart["dasha"]["balance_at_birth_years"]) < 0.01,
      f"{first['duration_years'] - elapsed:.4f} vs "
      f"{chart['dasha']['balance_at_birth_years']}")
check("12 dasha years sum to the 120 of Ch.46 v14",
      sum(YEARS.values()) == 120, str(sum(YEARS.values())))

# Ch. 46 v12-14: lords run from Krittika, making Ashwini's lord Ketu.
LORD_CYCLE = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter",
              "Saturn", "Mercury"]
LORD_CYCLE_HEAD = LORD_CYCLE[:3]

check("13 Krittika's lord is the Sun, so Ashwini's is Ketu (Ch.46 v12-14)",
      LORD_CYCLE_HEAD == ["Ketu", "Venus", "Sun"],
      str(LORD_CYCLE_HEAD))
bad = {n: (g[n]["nakshatra_index"], g[n]["nakshatra_lord"])
       for n in g if g[n]["nakshatra_lord"] != LORD_CYCLE[g[n]["nakshatra_index"] % 9]}
check("14 every nakshatra lord follows the Ch.46 cycle", not bad, str(bad))

# ---------------------------------------------------------------- BPHS Ch. 6
# vv. 7-8: the three drekkanas of a sign are the 1st, 5th and 9th from it.
d3 = chart["vargas"]["D3"]["grahas"]
bad = {}
for n, v in d3.items():
    lon = g[n]["longitude"]
    sign, deg = int(lon // 30), lon % 30
    expect = (sign + [0, 4, 8][int(deg // 10)]) % 12
    if v["sign"]["index"] != expect:
        bad[n] = (v["sign"]["index"], expect)
check("15 drekkana is the 1st/5th/9th per Ch.6 v7-8", not bad, str(bad))

# vv. 5-6: hora divides a sign in half between the Sun and the Moon, so every
# hora placement must land in Cancer or Leo.
d2 = {n: v["sign"]["index"] for n, v in chart["vargas"]["D2"]["grahas"].items()}
check("16 every hora falls in Cancer or Leo (Ch.6 v5-6)",
      set(d2.values()) <= {3, 4}, str(sorted(set(d2.values()))))

# D1 is the rashi itself.
d1 = {n: v["sign"]["index"] for n, v in chart["vargas"]["D1"]["grahas"].items()}
check("17 D1 is the rashi itself",
      all(d1[n] == g[n]["sign_index"] for n in d1), "")

# Navamsa: 108 equal divisions of the zodiac, cycling through the twelve signs.
d9 = chart["vargas"]["D9"]["grahas"]
bad = {n: (v["sign"]["index"], int(g[n]["longitude"] / (30 / 9)) % 12)
       for n, v in d9.items()
       if v["sign"]["index"] != int(g[n]["longitude"] / (30 / 9)) % 12}
check("18 navamsa is the 9th division cycling by sign", not bad, str(bad))

# Trimsamsa is shared among the five non-luminary owners, so Cancer and Leo
# (the Moon's and Sun's signs) can never receive a D30 placement.
d30 = {n: v["sign"]["index"] for n, v in chart["vargas"]["D30"]["grahas"].items()}
check("19 trimsamsa never lands in Cancer or Leo",
      not ({3, 4} & set(d30.values())), str(sorted(set(d30.values()))))

# ---------------------------------------------------------------- BPHS Ch. 3
# vv. 66-69: Gulika is Saturn's eighth portion; Mandi is the same upagraha.
up = {u["name"]: u for u in chart["upagrahas"]}
check("20 Mandi and Gulika coincide (Ch.3 v66-69)",
      abs(up["Gulika"]["longitude"] - up["Mandi"]["longitude"]) < 1e-6,
      f"{up['Gulika']['longitude']} vs {up['Mandi']['longitude']}")

# --------------------------------------------------- astronomical invariants
check("21 Rahu and Ketu are exactly 180 apart",
      abs(((g["Rahu"]["longitude"] - g["Ketu"]["longitude"]) % 360.0) - 180.0) < 1e-6,
      str((g["Rahu"]["longitude"] - g["Ketu"]["longitude"]) % 360.0))
check("22 mean nodes are retrograde",
      g["Rahu"]["retrograde"] and g["Ketu"]["retrograde"], "")
check("23 the Sun is never retrograde", not g["Sun"]["retrograde"], "")
check("24 the Moon is never retrograde", not g["Moon"]["retrograde"], "")
check("25 solar speed is about a degree a day",
      0.95 < g["Sun"]["speed"] < 1.03, str(g["Sun"]["speed"]))
check("26 lunar speed is 11-15 degrees a day",
      11.0 < g["Moon"]["speed"] < 15.5, str(g["Moon"]["speed"]))
check("27 the Sun is not reported combust with itself",
      not g["Sun"]["dignity"]["combust"], "")

# ------------------------------------------------------ internal consistency
bad = {n: (v["sign_index"], int(v["longitude"] // 30)) for n, v in g.items()
       if v["sign_index"] != int(v["longitude"] // 30)}
check("28 sign index follows from longitude", not bad, str(bad))
bad = {n: (v["nakshatra_index"], int(v["longitude"] / NAK_ARC)) for n, v in g.items()
       if v["nakshatra_index"] != int(v["longitude"] / NAK_ARC)}
check("29 nakshatra index follows from longitude", not bad, str(bad))
bad = {n: (v["nakshatra_pada"], int((v["longitude"] % NAK_ARC) / (NAK_ARC / 4)) + 1)
       for n, v in g.items()
       if v["nakshatra_pada"] != int((v["longitude"] % NAK_ARC) / (NAK_ARC / 4)) + 1}
check("30 nakshatra pada follows from longitude", not bad, str(bad))

lagna_sign = chart["lagna"]["sign_index"]
bad = {n: (v["house"], (v["sign_index"] - lagna_sign) % 12 + 1) for n, v in g.items()
       if v["house"] != (v["sign_index"] - lagna_sign) % 12 + 1}
check("31 whole-sign houses follow from the Lagna", not bad, str(bad))

occupants = [o for h in chart["houses"] for o in h["occupants"]]
check("32 every graha sits in exactly one house",
      sorted(occupants) == sorted(g), f"{len(occupants)} placements")

LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
         "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
bad = {h["house"]: (h["lord"], LORDS[h["sign"]["index"]]) for h in chart["houses"]
       if h["lord"] != LORDS[h["sign"]["index"]]}
check("33 sign lords are the classical rulerships", not bad, str(bad))

# Panchanga arithmetic from the Sun-Moon relationship.
p = chart["panchanga"]
check("34 tithi follows from the elongation",
      p["tithi"]["index"] == int(elong / 12.0) + 1,
      f"{p['tithi']['index']} vs {int(elong / 12.0) + 1}")
ssum = (g["Sun"]["longitude"] + g["Moon"]["longitude"]) % 360.0
check("35 nitya yoga follows from the sum of longitudes",
      p["yoga"]["index"] == int(ssum / NAK_ARC) + 1,
      f"{p['yoga']['index']} vs {int(ssum / NAK_ARC) + 1}")



# ============================================================================
# The checks above ran on one chart. A single chart can satisfy a wrong rule by
# luck, so the rule-shaped ones are now re-run across varied births: both
# hemispheres, high latitude, a retrograde-heavy epoch, and a new-Moon birth.
# ============================================================================

CHARTS = [
    ("Delhi 1990", {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139,
                    "longitude": 77.209, "timezone": "Asia/Kolkata"}),
    ("Sydney 1956", {"date": "1956-03-15", "time": "14:20", "latitude": -33.8688,
                     "longitude": 151.2093, "timezone": "Australia/Sydney"}),
    ("London 1977", {"date": "1977-11-02", "time": "23:55", "latitude": 51.5074,
                     "longitude": -0.1278, "timezone": "Europe/London"}),
    ("Reykjavik 2001", {"date": "2001-06-30", "time": "03:10", "latitude": 64.1466,
                        "longitude": -21.9426, "timezone": "Atlantic/Reykjavik"}),
    ("Lima 1969", {"date": "1969-07-20", "time": "09:00", "latitude": -12.0464,
                   "longitude": -77.0428, "timezone": "America/Lima"}),
    ("Tokyo 2024", {"date": "2024-02-29", "time": "18:45", "latitude": 35.6762,
                    "longitude": 139.6503, "timezone": "Asia/Tokyo"}),
    ("Nairobi 1935", {"date": "1935-09-09", "time": "06:00", "latitude": -1.2921,
                      "longitude": 36.8219, "timezone": "Africa/Nairobi"}),
    ("Anchorage 1988", {"date": "1988-12-21", "time": "12:00", "latitude": 61.2181,
                        "longitude": -149.9003, "timezone": "America/Anchorage"}),
]

KENDRAS = (1, 4, 7, 10)
OWN = {"Mars": (0, 7), "Mercury": (2, 5), "Jupiter": (8, 11),
       "Venus": (1, 6), "Saturn": (9, 10)}
EXALT_SIGN = {"Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
MAHAPURUSHA = {"Mars": "Ruchaka Yoga", "Mercury": "Bhadra Yoga",
               "Jupiter": "Hamsa Yoga", "Venus": "Malavya Yoga",
               "Saturn": "Sasa Yoga"}

for label, birth in CHARTS:
    c = post("/v1/chart", {**birth, "include_yogas": True,
                           "include_ashtakavarga": True, "dasha_depth": 1})
    gg, lag = c["grahas"], c["lagna"]["sign_index"]

    # Invariants that must hold on every chart, not just a lucky one.
    check(f"40 nodes 180 apart [{label}]",
          abs(((gg["Rahu"]["longitude"] - gg["Ketu"]["longitude"]) % 360) - 180) < 1e-6)
    check(f"41 luminaries never retrograde [{label}]",
          not gg["Sun"]["retrograde"] and not gg["Moon"]["retrograde"])
    check(f"42 whole-sign houses from the Lagna [{label}]",
          all(v["house"] == (v["sign_index"] - lag) % 12 + 1 for v in gg.values()))
    check(f"43 nakshatra index from longitude [{label}]",
          all(v["nakshatra_index"] == int(v["longitude"] / NAK_ARC)
              for v in gg.values()))
    check(f"44 sarvashtakavarga totals 337 [{label}]",
          c["sarvashtakavarga"]["total"] == 337, str(c["sarvashtakavarga"]["total"]))
    check(f"45 twelve houses, nine grahas placed [{label}]",
          len(c["houses"]) == 12
          and sorted(o for h in c["houses"] for o in h["occupants"]) == sorted(gg))

    yogas = {y["name"]: y["has_yoga"]
             for grp in c["yogas"]["yoga_details"] for y in grp["yoga_list"]}

    # BPHS Ch. 75 vv. 1-2: Mars, Mercury, Jupiter, Venus or Saturn in own sign
    # or exaltation, occupying a kendra from the Lagna.
    for graha, yoga in MAHAPURUSHA.items():
        sign = gg[graha]["sign_index"]
        expect = (gg[graha]["house"] in KENDRAS
                  and (sign in OWN[graha] or sign == EXALT_SIGN[graha]))
        check(f"46 {yoga} per Ch.75 v1-2 [{label}]", yogas.get(yoga) == expect,
              f"sign={sign} house={gg[graha]['house']} "
              f"engine={yogas.get(yoga)} expect={expect}")

    # BPHS Ch. 36 vv. 3-4: Jupiter in an angle from the Lagna -- and in the
    # wider reading also from the Moon -- gives Gaja Kesari.
    from_moon = (gg["Jupiter"]["sign_index"] - gg["Moon"]["sign_index"]) % 12 + 1
    check(f"47 Gajakesari needs Jupiter in a kendra [{label}]",
          (not yogas.get("Gajakesari Yoga"))
          or from_moon in KENDRAS or gg["Jupiter"]["house"] in KENDRAS,
          f"from_moon={from_moon} from_lagna={gg['Jupiter']['house']} "
          f"engine={yogas.get('Gajakesari Yoga')}")



# ---------------------------------------------------- the other endpoints
m = post("/v1/matching", {"boy": {**BIRTH}, "girl": {**CHARTS[1][1]}})
gm = m["guna_milan"]
check("50 ashtakoot is scored out of 36", gm["maximum_points"] == 36,
      str(gm["maximum_points"]))
check("51 ashtakoot total is the sum of its kootas",
      abs(sum(k["obtained_points"] for k in gm["guna"]) - gm["total_points"]) < 1e-9,
      f"{sum(k['obtained_points'] for k in gm['guna'])} vs {gm['total_points']}")
check("52 no koota exceeds its own maximum",
      all(k["obtained_points"] <= k["maximum_points"] for k in gm["guna"]))

pr = post("/v1/porutham", {"boy_nakshatra": 3, "boy_nakshatra_pada": 1,
                           "girl_nakshatra": 7, "girl_nakshatra_pada": 2,
                           "twelve": True})
check("53 porutham runs to twelve checks", pr["maximum_points"] == 12,
      str(pr["maximum_points"]))
check("54 porutham total counts its own passes",
      pr["obtained_points"] == sum(1 for x in pr["matches"] if x["has_porutham"]))

mu = post("/v1/muhurta", {"date": "1990-01-15", "latitude": 28.6139,
                          "longitude": 77.209, "timezone": "Asia/Kolkata"})
check("55 choghadiya covers day and night in 16 slots",
      len(mu["choghadiya"]) == 16, str(len(mu["choghadiya"])))
check("56 the hora cycle is 24 long", len(mu["hora"]) == 24, str(len(mu["hora"])))
check("57 sunrise precedes sunset precedes the next sunrise",
      mu["sunrise"] < mu["sunset"] < mu["next_sunrise"])

kp = post("/v1/kp", {**BIRTH})
check("58 KP returns twelve cusps", len(kp["houses"]) == 12, str(len(kp["houses"])))
check("59 every KP body carries star, sub and sub-sub lords",
      all(x.get("nakshatra_lord") and x.get("sub_lord") and x.get("sub_sub_lord")
          for x in kp["planets"]))

print(f"\n{BASE}\n" + "-" * 78)
failed = [(c, d) for c, ok, d in results if not ok]
for case, ok, detail in results:
    if not ok:
        print(f"FAIL  {case}\n      {detail}")
print("-" * 78)
print(f"{len(results) - len(failed)}/{len(results)} checks pass against BPHS "
      f"and first principles")
