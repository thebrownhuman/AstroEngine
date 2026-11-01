"""Shadbala and bhava bala against Raman's Standard Horoscope.

Every expected number is printed in B. V. Raman, *Graha and Bhava Balas*
(female, 16 Oct 1918, 14:06:16 LMT, 13 N, 77 E 35). Inputs are his printed
longitudes, ayanamsa, Lagna and MC, so these tests check the arithmetic, not
the ephemeris. Tolerance is 0.1 virupa; where Raman's own arithmetic slips the
expected value is our recomputation and ERRATA says what he printed and why
(also in docs/shadbala-notes.md).
"""
import pytest
from fastapi.testclient import TestClient

from astro_engine import shadbala as sb
from astro_engine.api import app


def dms(d, m=0, s=0):
    return d + m / 60 + s / 3600


LONGITUDES = {
    "Sun": dms(180, 53, 55), "Moon": dms(311, 17, 19), "Mars": dms(229, 30, 34),
    "Mercury": dms(181, 31, 34), "Jupiter": dms(84, 0, 49),
    "Venus": dms(171, 9, 56), "Saturn": dms(124, 22, 41),
}
MOMENT = sb.Moment(
    apparent_hours=dms(14, 20),                 # Example 17: 2-20 p.m. LAT
    is_day=True,
    part_fraction=dms(20, 32) / dms(29, 20),    # Gh. 20-32 of an ahas of 29-20
    hours_since_sunrise=dms(20, 32) * 0.4,      # ghatis to hours
    ahargana=33405,                             # Example 23
    chesta_interval=6862 + 14 / 24,             # Example 39
    year=1918,
)
RESULT = sb.compute(LONGITUDES, ayanamsa=dms(21, 16), ascendant=dms(298, 27),
                    midheaven=dms(216, 36), moment=MOMENT)
P = RESULT["planets"]
TOL = 0.1

# (planet, field): (Raman's printed value, the value he should have got)
ERRATA = {
    # Ex. 3: 111 30' 34" / 3 is 37.17, printed 37.06.
    ("Mars", "uchcha"): (37.06, 37.17),
    # Ex. 33: Mars kranti 22.43 (he writes 22.45) gives 1.96, printed 1.84.
    ("Mars", "ayana"): (1.84, 1.96),
    # Ex. 32: 1238' + 147' = 1385' = 23 05', read as 23.5 degrees.
    ("Jupiter", "ayana"): (59.40, 58.86),
    # Ex. 32: 703' + 4 21'/15 x 299' = 790' = 13.16 degrees, used as 13.0.
    ("Saturn", "ayana"): (13.75, 13.55),
}


def expect(planet, field, printed):
    return ERRATA.get((planet, field), (printed, printed))[1]


@pytest.mark.parametrize("planet,printed", [
    ("Sun", 3.00), ("Moon", 32.75), ("Mars", 37.06), ("Mercury", 54.50),
    ("Jupiter", 56.33), ("Venus", 1.95), ("Saturn", 34.80),
])
def test_uchcha_bala(planet, printed):
    assert P[planet]["sthana"]["uchcha"] == pytest.approx(expect(planet, "uchcha", printed), abs=TOL)


@pytest.mark.parametrize("planet,printed", [
    ("Sun", 90.0), ("Moon", 48.75), ("Mars", 90.0), ("Mercury", 135.0),
    ("Jupiter", 71.25), ("Venus", 116.25), ("Saturn", 97.5),
])
def test_saptavargaja_bala(planet, printed):
    assert P[planet]["sthana"]["saptavargaja"] == pytest.approx(printed, abs=TOL)


def test_saptavarga_grades_match_example_6():
    assert P["Sun"]["saptavarga_grades"] == {
        "D1": "Neutral", "D2": "own", "D3": "Neutral", "D7": "Neutral",
        "D9": "Neutral", "D12": "Neutral", "D30": "Extreme Friend"}
    assert P["Venus"]["saptavarga_grades"]["D3"] == "own"
    assert P["Venus"]["saptavarga_grades"]["D12"] == "own"


@pytest.mark.parametrize("planet,oja,kendra,drekkana,total", [
    ("Sun", 30, 60, 15, 198.00), ("Moon", 15, 30, 0, 126.50),
    ("Mars", 15, 30, 0, 172.17), ("Mercury", 30, 60, 0, 279.50),
    ("Jupiter", 15, 15, 0, 157.58), ("Venus", 30, 15, 15, 178.20),
    ("Saturn", 15, 30, 0, 177.30),
])
def test_rest_of_sthana_bala(planet, oja, kendra, drekkana, total):
    s = P[planet]["sthana"]
    assert (s["ojayugma"], s["kendra"], s["drekkana"]) == (oja, kendra, drekkana)
    # Mars: 172.06 printed, off by his uchcha slip.
    assert s["total"] == pytest.approx(total, abs=TOL)


@pytest.mark.parametrize("planet,printed", [
    ("Sun", 48.10), ("Moon", 31.56), ("Mars", 55.70), ("Mercury", 21.09),
    ("Jupiter", 11.50), ("Venus", 15.15), ("Saturn", 58.02),
])
def test_dig_bala(planet, printed):
    assert P[planet]["dig"] == pytest.approx(printed, abs=TOL)


@pytest.mark.parametrize("planet,natha,paksha", [
    ("Sun", 48.32, 16.54), ("Moon", 11.68, 86.92), ("Mars", 11.68, 16.54),
    ("Mercury", 60.0, 16.54), ("Jupiter", 48.32, 43.46),
    ("Venus", 48.32, 43.46), ("Saturn", 11.68, 16.54),
])
def test_nathonnata_and_paksha(planet, natha, paksha):
    k = P[planet]["kala"]
    assert k["nathonnata"] == pytest.approx(natha, abs=TOL)
    assert k["paksha"] == pytest.approx(paksha, abs=TOL)


def test_tribhaga_and_lords_of_time():
    assert RESULT["lords_of_time"] == {
        "abda": "Saturn", "masa": "Mercury", "vara": "Mercury", "hora": "Moon"}
    assert {p for p in sb.PLANETS if P[p]["kala"]["tribhaga"]} == {"Saturn", "Jupiter"}
    assert P["Saturn"]["kala"]["abda"] == 15
    assert P["Mercury"]["kala"]["masa"] == 30
    assert P["Mercury"]["kala"]["vara"] == 45
    assert P["Moon"]["kala"]["hora"] == 60


@pytest.mark.parametrize("planet,printed", [
    ("Sun", 38.12), ("Moon", 43.44), ("Mars", 1.84), ("Mercury", 41.25),
    ("Jupiter", 59.40), ("Venus", 23.75), ("Saturn", 13.75),
])
def test_ayana_bala(planet, printed):
    assert P[planet]["kala"]["ayana"] == pytest.approx(expect(planet, "ayana", printed), abs=TOL)


@pytest.mark.parametrize("planet,printed", [
    ("Sun", 102.98), ("Moon", 202.04), ("Mercury", 192.79), ("Venus", 115.53),
])
def test_kala_bala_totals(planet, printed):
    assert P[planet]["kala"]["total"] == pytest.approx(printed, abs=TOL)


def test_no_yuddha_in_the_standard_horoscope():
    assert all(P[p]["kala"]["yuddha"] == 0 for p in sb.PLANETS)


@pytest.mark.parametrize("planet,kendra,bala", [
    ("Mars", 293.31, 22.23), ("Mercury", 353.11, 2.30), ("Jupiter", 105.77, 35.26),
    ("Venus", 342.15, 5.95), ("Saturn", 63.42, 21.14),
])
def test_chesta_bala(planet, kendra, bala):
    # Raman's Jupiter tables disagree with each other by 0.1 degree of mean
    # longitude, worth 0.05 of kendra; inside tolerance either way.
    assert P[planet]["chesta_kendra"] == pytest.approx(kendra, abs=0.1)
    assert P[planet]["chesta"] == pytest.approx(bala, abs=TOL)


def test_mean_positions_example_99_and_104():
    means = sb.mean_positions(MOMENT)
    assert means["seeghrochcha"]["Mars"] == pytest.approx(181.23, abs=0.02)
    assert means["mean"]["Mars"] == pytest.approx(266.34, abs=0.02)
    # His table rows sum to 0.04 under rate x interval.
    assert means["mean"]["Saturn"] == pytest.approx(111.23, abs=0.05)
    assert means["seeghrochcha"]["Mercury"] == pytest.approx(174.49, abs=0.05)
    assert means["seeghrochcha"]["Venus"] == pytest.approx(158.35, abs=0.05)
    assert means["mean"]["Jupiter"] == pytest.approx(66.91, abs=0.12)


def test_naisargika_bala():
    expected = {"Sun": 60.0, "Moon": 51.43, "Venus": 42.86, "Jupiter": 34.29,
                "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57}
    for planet, value in expected.items():
        assert P[planet]["naisargika"] == pytest.approx(value, abs=0.02)


@pytest.mark.parametrize("planet,pinda,drik", [
    ("Sun", 63.45, 15.86), ("Moon", -86.93, -21.73), ("Mars", 3.81, 0.95),
    ("Mercury", 62.57, 15.64), ("Jupiter", -64.14, -16.04),
    ("Venus", 73.88, 18.47), ("Saturn", 28.82, 7.21),
])
def test_drik_bala(planet, pinda, drik):
    assert P[planet]["drishti_pinda"] == pytest.approx(pinda, abs=0.2)
    assert P[planet]["drik"] == pytest.approx(drik, abs=TOL)


# Example 56. Sun printed 424.24 for 424.94 (his rupas, 7.08, are right);
# Mercury 537.02 with rupas 8.85 for 8.95. The Mars, Jupiter and Saturn
# totals carry the errata above.
TOTALS = {"Sun": 424.94, "Moon": 389.80, "Mars": 298.37, "Mercury": 537.02,
          "Jupiter": 433.25, "Venus": 376.15, "Saturn": 388.97}


@pytest.mark.parametrize("planet", sb.PLANETS)
def test_shadbala_totals(planet):
    assert P[planet]["total_virupas"] == pytest.approx(TOTALS[planet], abs=TOL)
    assert P[planet]["total_rupas"] == pytest.approx(TOTALS[planet] / 60, abs=0.01)


def test_minimum_required_ratio_example_57():
    ratios = {p: P[p]["strength_ratio"] for p in sb.PLANETS}
    assert ratios["Sun"] == pytest.approx(1.42, abs=0.01)
    assert ratios["Moon"] == pytest.approx(1.08, abs=0.01)
    assert ratios["Mars"] == pytest.approx(0.99, abs=0.01)
    assert ratios["Saturn"] == pytest.approx(1.30, abs=0.01)
    # "Mars is the least powerful, and Ravi is the most powerful planet."
    assert P["Sun"]["rank"] == 1 and P["Mars"]["rank"] == 7
    assert not P["Mars"]["is_strong"] and P["Sun"]["is_strong"]


@pytest.mark.parametrize("planet,ishta,kashta", [
    ("Sun", 8.25, 46.13), ("Moon", 37.73, 21.23), ("Mars", 28.70, 29.44),
    ("Mercury", 11.20, 17.83), ("Jupiter", 44.57, 9.52),
    ("Venus", 3.40, 56.00), ("Saturn", 27.00, 31.30),
])
def test_ishta_kashta_phala(planet, ishta, kashta):
    # Mars uses the corrected uchcha (37.17); Raman's Mercury kashta line
    # (49.16) multiplies by 60 - 1.30 instead of 60 - 2.30; the true value
    # sqrt(5.5 x 57.7) is 17.8. Saturn: sqrt(34.8 x 21.14) = 27.12.
    assert P[planet]["ishta_phala"] == pytest.approx(ishta, abs=0.15)
    assert P[planet]["kashta_phala"] == pytest.approx(kashta, abs=0.15)


# Example 59: (drishti, dig, total). Totals use our lord shadbala, so they
# move with the errata; Bhava XII's printed total 426.76 is 526.76 misprinted.
BHAVAS = {
    1: (54.18, 30, 473.15), 2: (36.44, 40, 509.71), 3: (58.99, 10, 367.39),
    4: (28.10, 0, 404.21), 5: (11.57, 20, 568.50), 6: (2.92, 40, 432.75),
    7: (5.70, 30, 425.45), 8: (32.51, 10, 579.31), 9: (44.80, 20, 440.95),
    10: (44.51, 30, 372.90), 11: (33.12, 40, 506.15), 12: (97.55, 40, 526.56),
}


@pytest.mark.parametrize("bhava", range(1, 13))
def test_bhava_bala(bhava):
    row = RESULT["bhavas"][bhava - 1]
    drishti, dig, total = BHAVAS[bhava]
    assert row["dig"] == dig
    # Raman's Saturn-on-Bhava-I entry reads 13.00 for 12.03 (net 54.18 is
    # consistent with 12.03); 0.25 covers his per-cell rounding (Bhava XI
    # sums eight rounded cells to 33.12 against 32.89 unrounded).
    assert row["drishti"] == pytest.approx(drishti, abs=0.25)
    assert row["total_virupas"] == pytest.approx(total, abs=0.2)


def test_bhava_lords_and_ranking():
    lords = [row["lord"] for row in RESULT["bhavas"]]
    assert lords == ["Saturn", "Jupiter", "Mars", "Venus", "Mercury", "Moon",
                     "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
    ranks = {row["bhava"]: row["rank"] for row in RESULT["bhavas"]}
    # Art. 134: "the 8th is the most powerful bhava while the 3rd is the least".
    assert ranks[8] == 1 and ranks[3] == 12


def test_sripati_madhyas_reproduce_example_8():
    madhyas = sb.sripati_madhyas(dms(298, 27), dms(216, 36))
    printed = [(298, 27), (331, 10), (3, 53), (36, 36), (63, 53), (91, 10),
               (118, 27), (151, 10), (183, 53), (216, 36), (243, 53), (271, 10)]
    for got, (d, m) in zip(madhyas, printed):
        assert got == pytest.approx(dms(d, m), abs=0.02)


def test_drishti_value_curve():
    assert [sb.drishti_value(k) for k in (0, 30, 60, 90, 120, 150, 180, 240, 300)] == [
        0, 0, 15, 45, 30, 0, 60, 30, 0]
    assert sb.visesha("Saturn", 75) == 45 and sb.visesha("Saturn", 120) == 0


def test_yuddha_moves_strength_from_loser_to_winner():
    longitudes = dict(LONGITUDES, Venus=dms(181, 0))  # 31' behind Mercury
    result = sb.compute(longitudes, ayanamsa=dms(21, 16), ascendant=dms(298, 27),
                        midheaven=dms(216, 36), moment=MOMENT)["planets"]
    venus, mercury = result["Venus"]["kala"]["yuddha"], result["Mercury"]["kala"]["yuddha"]
    assert venus > 0 and venus == pytest.approx(-mercury, abs=0.01)


def test_bphs_convention_changes_the_documented_points():
    bphs = sb.compute(LONGITUDES, ayanamsa=dms(21, 16), ascendant=dms(298, 27),
                      midheaven=dms(216, 36), moment=MOMENT, convention="bphs")["planets"]
    assert bphs["Sun"]["chesta"] == pytest.approx(P["Sun"]["kala"]["ayana"], abs=0.01)
    assert bphs["Moon"]["chesta"] == pytest.approx(P["Moon"]["kala"]["paksha"], abs=0.01)
    assert bphs["Moon"]["sthana"]["drekkana"] == 15  # female, second drekkana
    assert bphs["Sun"]["sthana"]["saptavargaja"] == 30 + 6 * 10 + 20 - 10  # 100
    with pytest.raises(ValueError):
        sb.compute(LONGITUDES, ayanamsa=0, ascendant=0, midheaven=270,
                   moment=MOMENT, convention="other")


# --- API ----------------------------------------------------------------------

client = TestClient(app)
BIRTH = {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139,
         "longitude": 77.2090, "timezone": "Asia/Kolkata"}


def test_chart_default_shape_has_no_shadbala():
    body = client.post("/v1/chart", json=BIRTH).json()
    assert "shadbala" not in body


def test_chart_include_shadbala_and_endpoint_agree():
    chart = client.post("/v1/chart", json={**BIRTH, "include_shadbala": True}).json()
    direct = client.post("/v1/shadbala", json=BIRTH).json()
    assert chart["shadbala"]["planets"] == direct["planets"]
    planets = direct["planets"]
    assert set(planets) == set(sb.PLANETS)
    assert len(direct["bhavas"]) == 12
    for block in direct["sources"].values():
        assert block["source"] in {"bphs", "classical"}
    for p in sb.PLANETS:
        assert 150 < planets[p]["total_virupas"] < 800
        assert 0 <= planets[p]["ishta_phala"] <= 60


def test_shadbala_endpoint_rejects_polar_night():
    body = {**BIRTH, "date": "1990-12-21", "latitude": 78.2, "longitude": 15.6,
            "timezone": "Arctic/Longyearbyen"}
    assert client.post("/v1/shadbala", json=body).status_code == 422
