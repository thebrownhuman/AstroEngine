"""strict_bphs: each departure from the book flips under the flag, and the
default output stays exactly what it was."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import swisseph as swe

from astro_engine import ashtakavarga as av
from astro_engine import yogas
from astro_engine.api import app
from astro_engine.chart import BirthData, build
from astro_engine.dasha import NAKSHATRA_ARC, bhayata_fraction
from astro_engine.ephemeris import SiderealScanner

client = TestClient(app)

BIRTH = {"date": "1990-01-15", "time": "04:30", "latitude": 28.6139,
         "longitude": 77.209, "timezone": "Asia/Kolkata"}
FULL = {**BIRTH, "include_ashtakavarga": True, "include_upagrahas": True,
        "include_yogas": True}


def _birth(strict: bool) -> BirthData:
    return BirthData(1990, 1, 15, 4, 30, 0, 28.6139, 77.209, "Asia/Kolkata",
                     strict_bphs=strict)


@pytest.fixture(scope="module")
def default():
    return client.post("/v1/chart", json=FULL).json()


@pytest.fixture(scope="module")
def strict():
    return client.post("/v1/chart", json={**FULL, "strict_bphs": True}).json()


def test_conflicting_conventions_are_rejected():
    r = client.post("/v1/chart", json={**BIRTH, "strict_bphs": True,
                                       "prokerala_compatible": True})
    assert r.status_code == 422
    assert "strict_bphs" in r.text


def test_explicit_false_is_the_default(default):
    explicit = client.post("/v1/chart", json={**FULL, "strict_bphs": False}).json()
    for body in (default, explicit):
        body["current_dasha"].pop("as_of")
        body["current_dasha"].pop("chain")
    assert json.dumps(explicit, sort_keys=True) == json.dumps(default, sort_keys=True)
    assert "strict_bphs" not in default["engine"]


def test_engine_is_stamped(strict):
    assert strict["engine"]["strict_bphs"] is True


def test_dignity_state_is_the_bphs_state(default, strict):
    for name, g in strict["grahas"].items():
        assert g["dignity"]["state"] == g["dignity"]["bphs_state"], name
    assert strict["sources"]["dignity"]["source"] == "bphs"
    assert default["sources"]["dignity"]["authority"] != strict["sources"]["dignity"]["authority"]


def test_dasha_balance_uses_bhayata(default, strict):
    jd = strict["input"]["julian_day_ut"]
    scanner = SiderealScanner()
    fraction = bhayata_fraction(lambda t: scanner.longitude(t, swe.MOON), jd)
    years = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
             "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
    lord = strict["dasha"]["birth_dasha_lord"]
    assert strict["dasha"]["balance_at_birth_years"] == pytest.approx(
        (1 - fraction) * years[lord], abs=1e-5)
    moon = default["grahas"]["Moon"]["longitude"]
    arc = (moon % NAKSHATRA_ARC) / NAKSHATRA_ARC
    assert default["dasha"]["balance_at_birth_years"] == pytest.approx(
        (1 - arc) * years[lord], abs=1e-5)
    # About 19 days apart on this birth.
    gap = abs(strict["dasha"]["balance_at_birth_years"]
              - default["dasha"]["balance_at_birth_years"]) * 365.25
    assert 15 < gap < 25
    assert strict["sources"]["dasha"]["source"] == "bphs"


def test_bhayata_fraction_is_a_fraction():
    scanner = SiderealScanner()
    for jd in (2447906.5, 2451697.0, 2442736.6):
        f = bhayata_fraction(lambda t: scanner.longitude(t, swe.MOON), jd)
        assert 0.0 <= f < 1.0


def _upagraha(chart, name):
    return next(u for u in chart["upagrahas"] if u["name"] == name)


def test_gulika_moves_to_the_end_of_saturns_portion(default, strict):
    for name in ("Gulika", "Mandi"):
        assert _upagraha(strict, name)["longitude"] != _upagraha(default, name)["longitude"]
        assert _upagraha(strict, name)["source"] == "bphs"
        assert _upagraha(default, name)["source"] == "provider_compatible"
    for name in ("Kala", "Mrityu", "Dhuma"):
        assert _upagraha(strict, name)["longitude"] == _upagraha(default, name)["longitude"]


def test_ashtakavarga_cells_follow_the_sanskrit():
    assert av.table(True)["Moon"]["Moon"] == (1, 3, 6, 7, 9, 10, 11)
    assert av.table(True)["Moon"]["Mars"] == (2, 3, 5, 6, 10, 11)
    assert av.table(True)["Moon"]["Jupiter"] == (1, 2, 4, 7, 8, 10, 11)
    assert av.table(True)["Venus"]["Mars"] == (3, 4, 6, 9, 11, 12)
    assert av.table(False)["Moon"]["Moon"] == (1, 3, 6, 7, 10, 11)
    assert av.table(False)["Venus"]["Mars"] == (3, 5, 6, 9, 11, 12)
    changed = {(s, c) for s in av.SUBJECTS for c in av.CONTRIBUTORS
               if av.table(True)[s][c] != av.table(False)[s][c]}
    assert changed == {("Moon", "Moon"), ("Moon", "Mars"), ("Moon", "Jupiter"),
                       ("Venus", "Mars")}


def test_ashtakavarga_output_and_sources(default, strict):
    assert default["ashtakavarga"]["Moon"]["by_sign"] != strict["ashtakavarga"]["Moon"]["by_sign"]
    assert default["ashtakavarga"]["Sun"]["by_sign"] == strict["ashtakavarga"]["Sun"]["by_sign"]
    assert strict["sarvashtakavarga"]["total"] == 337
    assert strict["ashtakavarga_source"]["source"] == "bphs"
    assert strict["sarvashtakavarga"]["trikona"]["source"] == "bphs"
    assert strict["ashtakavarga"]["Sun"]["ekaadhipatya"]["source"] == "bphs"
    assert default["ashtakavarga_source"]["source"] == "provider_compatible"


def test_trikona_leaves_a_trine_with_a_zero():
    scores = [0, 1, 1, 1, 3, 1, 1, 1, 6, 1, 1, 1]
    assert av.trikona_shodhana(scores)[0::4] == [0, 0, 0]
    assert av.trikona_shodhana(scores, strict_bphs=True)[0::4] == [0, 3, 6]
    plain = [3, 2, 4, 2, 5, 1, 4, 3, 6, 2, 3, 5]
    assert av.trikona_shodhana(plain) == av.trikona_shodhana(plain, strict_bphs=True)


def test_ekadhipatya_tie_clears_the_planetless_sign():
    scores = [3] + [0] * 6 + [3] + [0] * 4
    assert av.ekadhipatya_shodhana(scores, {0})[7] == 3
    assert av.ekadhipatya_shodhana(scores, {0}, strict_bphs=True)[7] == 0
    assert av.ekadhipatya_shodhana(scores, {7}, strict_bphs=True)[0] == 0
    # Away from the tie the two agree.
    for scores, occ in (([5] + [0] * 6 + [3] + [0] * 4, {0}),
                        ([2] + [0] * 6 + [5] + [0] * 4, {0}),
                        ([2] + [0] * 6 + [2] + [0] * 4, set())):
        assert av.ekadhipatya_shodhana(scores, occ) == \
            av.ekadhipatya_shodhana(scores, occ, strict_bphs=True)


def _view(strict: bool, jupiter_sign: int, moon_sign: int, mercury_sign: int,
          jupiter_state: str = "neutral", combust: bool = False) -> yogas.ChartView:
    lagna = 0
    signs = {"Sun": 6, "Moon": moon_sign, "Mars": 6, "Mercury": mercury_sign,
             "Jupiter": jupiter_sign, "Venus": 6, "Saturn": 6, "Rahu": 2, "Ketu": 8}
    natures = {"Mercury": "benefic", "Venus": "benefic", "Moon": "benefic"}
    grahas = {
        g: {"sign_index": s, "house": (s - lagna) % 12 + 1,
            "nature": natures.get(g, "malefic"),
            "dignity": {"state": jupiter_state if g == "Jupiter" else "neutral",
                        "combust": combust if g == "Jupiter" else False}}
        for g, s in signs.items()
    }
    engine = {"strict_bphs": True} if strict else {}
    return yogas.ChartView({"grahas": grahas, "lagna": {"sign_index": lagna},
                            "engine": engine})


def test_gajakesari_allows_a_kendra_from_the_lagna():
    # Jupiter in Cancer (4th from the Aries Lagna), Moon in Taurus (3rd from
    # it), Mercury joining Jupiter.
    assert not yogas.gajakesari(_view(False, 3, 1, 3)).present
    found = yogas.gajakesari(_view(True, 3, 1, 3))
    assert found.present and found.as_dict()["source"] == "bphs"


def test_gajakesari_needs_a_benefic_and_a_sound_jupiter():
    # Jupiter in Cancer, Moon in Aries: a kendra from both.
    assert yogas.gajakesari(_view(False, 3, 0, 6)).present
    assert not yogas.gajakesari(_view(True, 3, 0, 6)).present           # no benefic link
    assert yogas.gajakesari(_view(True, 3, 0, 3)).present
    assert not yogas.gajakesari(_view(True, 3, 0, 3, combust=True)).present
    assert not yogas.gajakesari(_view(True, 9, 0, 9, "debilitated")).present
    assert not yogas.gajakesari(_view(True, 6, 0, 6)).present           # Libra, Venus's


def test_mahapurusha_counts_moolatrikona_as_own_sign():
    view = _view(True, 8, 0, 6, jupiter_state="moolatrikona")
    view.grahas["Jupiter"]["house"] = 10
    assert yogas.mahapurusha(view, "Jupiter").present


def test_build_accepts_the_flag_directly():
    chart = build(_birth(True), vargas=["D1"], dasha_depth=1)
    assert chart["engine"]["strict_bphs"] is True
    assert "strict_bphs" not in build(_birth(False), vargas=["D1"], dasha_depth=1)["engine"]
