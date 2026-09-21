from types import SimpleNamespace

from astro_engine.chart import (
    _aspects, _bphs_nature, _graha_aspect_targets, _rashi_aspected_signs,
    _rashi_aspects,
)


def test_rashi_aspects_follow_sign_modalities():
    assert _rashi_aspected_signs(0) == [4, 7, 10]       # Aries -> Leo, Scorpio, Aquarius
    assert _rashi_aspected_signs(1) == [3, 6, 9]        # Taurus -> Cancer, Libra, Capricorn
    assert _rashi_aspected_signs(2) == [5, 8, 11]       # Gemini -> Virgo, Sagittarius, Pisces


def test_rashi_aspects_include_signs_and_houses():
    positions = {
        "Sun": SimpleNamespace(sign_index=9),
        "Moon": SimpleNamespace(sign_index=1),
    }
    result = _rashi_aspects(positions, lagna_sign=7)
    sun = next(row for row in result if row["graha"] == "Sun")
    assert sun["aspects_houses"] == [7, 10, 1]
    assert sun["aspects_grahas"] == ["Moon"]


def test_bphs_does_not_give_nodes_special_graha_aspects():
    assert _graha_aspect_targets("Rahu", 0) == {6}
    assert _graha_aspect_targets("Ketu", 0) == {6}

    positions = {
        "Rahu": type("Position", (), {"sign_index": 0})(),
        "Sun": type("Position", (), {"sign_index": 4})(),
    }
    assert _aspects(positions, lagna_sign=0)[0]["aspects_houses"] == [7]


def test_bphs_contextual_nature_handles_moon_and_mercury_exceptions():
    positions = {
        "Sun": SimpleNamespace(sign_index=0, longitude=0.0),
        "Moon": SimpleNamespace(sign_index=6, longitude=200.0),
        "Mercury": SimpleNamespace(sign_index=6, longitude=190.0),
        "Jupiter": SimpleNamespace(sign_index=1, longitude=40.0),
        "Venus": SimpleNamespace(sign_index=1, longitude=50.0),
        "Mars": SimpleNamespace(sign_index=2, longitude=70.0),
        "Saturn": SimpleNamespace(sign_index=3, longitude=100.0),
        "Rahu": SimpleNamespace(sign_index=4, longitude=130.0),
        "Ketu": SimpleNamespace(sign_index=10, longitude=310.0),
    }
    assert _bphs_nature(positions, "Moon", 0.0)[0] == "benefic"
    assert _bphs_nature(positions, "Mercury", 0.0)[0] == "benefic"


def test_bphs_waning_moon_needs_a_benefic_join_or_aspect():
    positions = {
        "Sun": SimpleNamespace(sign_index=0, longitude=0.0),
        "Moon": SimpleNamespace(sign_index=6, longitude=200.0),
        "Mercury": SimpleNamespace(sign_index=1, longitude=40.0),
        "Jupiter": SimpleNamespace(sign_index=2, longitude=70.0),
        "Venus": SimpleNamespace(sign_index=1, longitude=50.0),
        "Mars": SimpleNamespace(sign_index=3, longitude=100.0),
        "Saturn": SimpleNamespace(sign_index=4, longitude=130.0),
        "Rahu": SimpleNamespace(sign_index=5, longitude=160.0),
        "Ketu": SimpleNamespace(sign_index=11, longitude=340.0),
    }
    # Jupiter in Gemini gives its BPHS 5th aspect to Libra, where the Moon is.
    assert _bphs_nature(positions, "Moon", 0.0)[0] == "benefic"

    positions["Jupiter"] = SimpleNamespace(sign_index=1, longitude=40.0)
    assert _bphs_nature(positions, "Moon", 0.0)[0] == "malefic"
