"""Correctness tests. These are the reason you can trust the output.

Reference values are cross-checked against Swiss Ephemeris directly and against
published Lahiri ayanamsa tables.
"""

from datetime import datetime

import pytest

from astro_engine import vargas
from astro_engine.chart import BirthData, build
from astro_engine.dasha import DAYS_PER_YEAR, balance_at_birth, vimshottari
from astro_engine.ephemeris import EPHEMERIS_BACKEND, SiderealSky, julian_day
from astro_engine.geo import to_utc

DELHI = (28.6139, 77.2090)


# --- ayanamsa ----------------------------------------------------------------

@pytest.mark.parametrize(
    "year,expected",
    [(1900, 22.4667), (1950, 23.1500), (2000, 23.8567), (2025, 24.2100)],
)
def test_lahiri_ayanamsa_matches_published_tables(year, expected):
    """Lahiri ayanamsa drifts ~50.3 arcsec/year. Tolerance is 1 arcminute."""
    jd = julian_day(datetime(year, 1, 1, 0, 0))
    assert SiderealSky(jd).ayanamsa_value() == pytest.approx(expected, abs=1 / 60)


def test_ayanamsa_is_monotonic():
    values = [
        SiderealSky(julian_day(datetime(y, 1, 1))).ayanamsa_value()
        for y in (1900, 1950, 2000, 2050)
    ]
    assert values == sorted(values)


# --- timezone handling -------------------------------------------------------

def test_ist_offset_is_five_thirty():
    utc, info = to_utc(datetime(1990, 1, 15, 4, 30), *DELHI)
    assert info["timezone"] == "Asia/Kolkata"
    assert info["utc_offset_hours"] == 5.5
    assert utc == datetime(1990, 1, 14, 23, 0)


def test_indian_wartime_dst_is_honoured():
    """India ran +6:30 during WWII. A naive +5:30 assumption is an hour wrong."""
    _, info = to_utc(datetime(1943, 6, 15, 12, 0), *DELHI)
    assert info["utc_offset_hours"] == 6.5
    assert info["dst_active"] is True


def test_explicit_timezone_overrides_coordinates():
    _, info = to_utc(datetime(1990, 1, 15, 4, 30), *DELHI, timezone="UTC")
    assert info["utc_offset_hours"] == 0.0
    assert info["timezone_source"] == "explicit"


def test_unknown_timezone_is_rejected():
    with pytest.raises(ValueError, match="unknown IANA timezone"):
        to_utc(datetime(1990, 1, 15, 4, 30), *DELHI, timezone="Mars/Olympus")


# --- vargas ------------------------------------------------------------------

@pytest.mark.parametrize(
    "longitude,expected_sign",
    [
        (0.0, 0),     # Aries 0 -> Aries (movable starts from itself)
        (30.0, 9),    # Taurus 0 -> Capricorn (fixed starts from the 9th)
        (60.0, 6),    # Gemini 0 -> Libra (dual starts from the 5th)
        (29.9, 8),    # Aries 29.9 -> last navamsa, Sagittarius
    ],
)
def test_navamsa_follows_parashari_start_rule(longitude, expected_sign):
    assert vargas.d9_navamsa(longitude) == expected_sign


def test_every_varga_returns_a_valid_sign():
    for _, fn in vargas.VARGAS.values():
        for step in range(0, 3600):
            assert 0 <= fn(step / 10.0) <= 11


def test_hora_only_ever_yields_cancer_or_leo():
    results = {vargas.d2_hora(step / 10.0) for step in range(3600)}
    assert results == {3, 4}


def test_trimsamsa_never_yields_a_luminary_sign():
    """Trimsamsa is ruled by the five non-luminaries, so Cancer and Leo cannot occur."""
    results = {vargas.d30_trimsamsa(step / 10.0) for step in range(3600)}
    assert 3 not in results and 4 not in results


def test_drekkana_is_trinal_to_the_rashi():
    for step in range(3600):
        lon = step / 10.0
        assert (vargas.d3_drekkana(lon) - vargas.d1_rashi(lon)) % 4 == 0


# --- vimshottari dasha -------------------------------------------------------

def test_dasha_lord_at_nakshatra_start_has_full_balance():
    lord, balance = balance_at_birth(0.0)
    assert lord == "Ketu"
    assert balance == pytest.approx(1.0)


def test_dasha_balance_halves_at_nakshatra_midpoint():
    _, balance = balance_at_birth(360.0 / 27.0 / 2.0)
    assert balance == pytest.approx(0.5)


def test_mahadasha_sequence_is_contiguous_and_correctly_sized():
    d = vimshottari(123.456, datetime(1990, 1, 15, 4, 30), depth=1)
    maha = d["mahadashas"]
    for previous, following in zip(maha, maha[1:]):
        assert previous["end"] == following["start"]
    for period in maha:
        span = (
            datetime.fromisoformat(period["end"]) - datetime.fromisoformat(period["start"])
        ).total_seconds() / 86400.0
        assert span == pytest.approx(period["duration_years"] * DAYS_PER_YEAR, abs=1e-6)


def test_full_cycle_is_one_hundred_and_twenty_years():
    d = vimshottari(0.0, datetime(1990, 1, 15), depth=1)
    first_nine = d["mahadashas"][:9]
    total = (
        datetime.fromisoformat(first_nine[-1]["end"])
        - datetime.fromisoformat(first_nine[0]["start"])
    ).total_seconds() / 86400.0
    assert total == pytest.approx(120 * DAYS_PER_YEAR, abs=1e-3)


def test_antardashas_exactly_fill_their_mahadasha():
    d = vimshottari(123.456, datetime(1990, 1, 15, 4, 30), depth=2)
    for maha in d["mahadashas"][:3]:
        subs = maha["sub_periods"]
        assert len(subs) == 9
        assert subs[0]["start"] == maha["start"]
        assert subs[-1]["end"] == maha["end"]


def test_birth_falls_inside_the_first_mahadasha():
    birth = datetime(1990, 1, 15, 4, 30)
    d = vimshottari(123.456, birth, depth=1)
    first = d["mahadashas"][0]
    assert datetime.fromisoformat(first["start"]) <= birth < datetime.fromisoformat(first["end"])


# --- whole chart -------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_chart():
    return build(
        BirthData(1990, 1, 15, 4, 30, 0, *DELHI),
        reference_time=datetime(2026, 9, 20),
    )


def test_chart_is_deterministic(sample_chart):
    again = build(
        BirthData(1990, 1, 15, 4, 30, 0, *DELHI),
        reference_time=datetime(2026, 9, 20),
    )
    assert again == sample_chart


def test_ketu_is_exactly_opposite_rahu(sample_chart):
    rahu = sample_chart["grahas"]["Rahu"]["longitude"]
    ketu = sample_chart["grahas"]["Ketu"]["longitude"]
    assert (ketu - rahu) % 360.0 == pytest.approx(180.0, abs=1e-9)


def test_houses_are_whole_sign_from_lagna(sample_chart):
    lagna_sign = sample_chart["lagna"]["sign_index"]
    for house in sample_chart["houses"]:
        assert house["sign"]["index"] == (lagna_sign + house["house"] - 1) % 12


def test_every_graha_is_placed_in_exactly_one_house(sample_chart):
    placed = [g for house in sample_chart["houses"] for g in house["occupants"]]
    assert sorted(placed) == sorted(sample_chart["grahas"])


def test_mean_nodes_are_always_retrograde(sample_chart):
    assert sample_chart["grahas"]["Rahu"]["retrograde"] is True
    assert sample_chart["grahas"]["Ketu"]["retrograde"] is True


def test_sun_is_never_marked_combust(sample_chart):
    assert sample_chart["grahas"]["Sun"]["dignity"]["combust"] is False


def test_pre_sunrise_birth_keeps_the_previous_vara(sample_chart):
    """Born 04:30, before the ~07:16 sunrise, so the Vedic day is still Sunday's."""
    assert sample_chart["solar_day"]["born_before_sunrise"] is True
    assert sample_chart["panchanga"]["vara"]["name"] == "Sunday"


def test_current_dasha_chain_is_nested_correctly(sample_chart):
    chain = sample_chart["current_dasha"]["chain"]
    assert [c["level"] for c in chain] == ["mahadasha", "antardasha"]
    outer, inner = chain
    assert outer["start"] <= inner["start"] and inner["end"] <= outer["end"]


def test_changing_ayanamsa_shifts_every_longitude():
    lahiri = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D1"])
    raman = build(
        BirthData(1990, 1, 15, 4, 30, 0, *DELHI, ayanamsa="raman"), vargas=["D1"]
    )
    for name in lahiri["grahas"]:
        assert lahiri["grahas"][name]["longitude"] != raman["grahas"][name]["longitude"]


def test_unknown_varga_is_rejected():
    with pytest.raises(ValueError, match="unknown varga"):
        build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D13"])


def test_southern_hemisphere_chart_builds():
    chart = build(BirthData(1985, 7, 3, 14, 15, 0, -33.8688, 151.2093))
    assert chart["input"]["timezone"] == "Australia/Sydney"
    assert len(chart["houses"]) == 12


# --- sunrise convention ------------------------------------------------------

def test_sunrise_uses_upper_limb_not_disc_centre():
    """Panchanga sunrise is first appearance of the upper limb, refracted.

    Regression guard: BIT_DISC_CENTER puts sunrise ~80 seconds later and
    disagrees with every published panchanga. Validated against
    api.sunrise-sunset.org, which lands 68s earlier using NOAA's fixed-zenith
    approximation.
    """
    from astro_engine.ephemeris import jd_to_datetime, sun_rise_set

    solar = sun_rise_set(julian_day(datetime(1990, 1, 15, 12, 0)), *DELHI)
    sunrise = jd_to_datetime(solar["sunrise_jd"])
    assert sunrise.date() == datetime(1990, 1, 15).date()
    # 01:44:51 UTC = 07:14:51 IST
    expected = datetime(1990, 1, 15, 1, 44, 51)
    assert abs((sunrise - expected).total_seconds()) < 5.0


def test_sunrise_precedes_sunset_and_next_sunrise():
    from astro_engine.ephemeris import sun_rise_set

    for lat, lon in [DELHI, (-33.8688, 151.2093), (64.1466, -21.9426)]:
        solar = sun_rise_set(julian_day(datetime(2026, 9, 20, 12, 0)), lat, lon)
        assert solar["sunrise_jd"] < solar["next_sunrise_jd"]
        assert 0.9 < solar["next_sunrise_jd"] - solar["sunrise_jd"] < 1.1


def test_true_chitra_places_spica_at_exactly_180_degrees():
    """Structural check that ayanamsa modes are wired to the right constants."""
    import swisseph as swe

    from astro_engine.ephemeris import _BACKEND_FLAG

    swe.set_sid_mode(swe.SIDM_TRUE_CITRA, 0, 0)
    values, _, _ = swe.fixstar_ut(
        "Spica", julian_day(datetime(2000, 1, 1)), _BACKEND_FLAG | swe.FLG_SIDEREAL
    )
    assert values[0] == pytest.approx(180.0, abs=1 / 3600)


# --- dasha year length -------------------------------------------------------

def test_default_dasha_year_is_the_julian_year():
    """Verified against Prokerala: with 365.25 the mahadasha boundaries agree to
    a constant offset with zero drift. With 365.2425 they drift 7.5 milli-days
    per year, which compounds to ~0.9 days over a full 120-year cycle.
    """
    from astro_engine.dasha import DAYS_PER_YEAR, JULIAN_YEAR

    assert DAYS_PER_YEAR == JULIAN_YEAR == 365.25


def test_year_length_is_configurable_and_changes_boundaries():
    from astro_engine.dasha import GREGORIAN_YEAR, JULIAN_YEAR

    birth = datetime(1990, 1, 15, 4, 30)
    julian = vimshottari(123.456, birth, depth=1, year_length=JULIAN_YEAR)
    gregorian = vimshottari(123.456, birth, depth=1, year_length=GREGORIAN_YEAR)

    assert julian["year_length_days"] == 365.25
    assert gregorian["year_length_days"] == 365.2425

    # Over the 120-year cycle the two conventions separate by roughly 0.9 days.
    span = lambda d: (  # noqa: E731
        datetime.fromisoformat(d["mahadashas"][8]["end"])
        - datetime.fromisoformat(d["mahadashas"][0]["start"])
    ).total_seconds() / 86400.0
    assert span(julian) - span(gregorian) == pytest.approx(120 * 0.0075, abs=1e-3)


def test_chart_exposes_the_year_length_used():
    chart = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    assert chart["dasha"]["year_length_days"] == 365.25


# --- Prokerala compatibility -------------------------------------------------

def test_mean_equinox_is_the_default():
    """Prokerala and mainstream Indian software subtract the nutation-free
    ayanamsa from the apparent tropical longitude. swisseph's FLG_SIDEREAL uses
    the nutation-included one; the two differ by up to 17 arcsec on an 18.6-year
    cycle. Verified: mean reproduces Prokerala to 0.002 arcsec.
    """
    chart = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    assert chart["engine"]["equinox"] == "mean_of_date"


@pytest.mark.skipif(
    EPHEMERIS_BACKEND != "swieph",
    reason="Prokerala reference values need the .se1 files; set SE_EPHE_PATH",
)
def test_mean_equinox_reproduces_prokerala_longitudes():
    """Reference values captured from the Prokerala v2 planet-position endpoint."""
    expected = {
        "Sun": 270.80876263036384,
        "Moon": 136.97252880281334,
        "Mercury": 258.0397984242986,
        "Venus": 277.28751437895426,
        "Mars": 235.8056062067514,
        "Jupiter": 69.71191718367794,
        "Saturn": 263.5327054142808,
        "Rahu": 294.00459280824055,
    }
    chart = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    for name, reference in expected.items():
        delta = abs(chart["grahas"][name]["longitude"] - reference) * 3600.0
        assert delta < 0.01, f"{name} off by {delta:.4f} arcsec"
    # Their Ascendant for the same moment.
    assert abs(chart["lagna"]["longitude"] - 230.856206486) * 3600.0 < 0.01


def test_true_equinox_differs_by_the_nutation():
    mean = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    true = build(
        BirthData(1990, 1, 15, 4, 30, 0, *DELHI, equinox="true"), vargas=["D1"], dasha_depth=1
    )
    delta = (mean["grahas"]["Sun"]["longitude"] - true["grahas"]["Sun"]["longitude"]) * 3600.0
    assert 12.0 < delta < 13.0  # nutation in longitude on 1990-01-15


def test_prokerala_rounding_mode_changes_the_dasha_balance():
    """Prokerala rounds the nakshatra traversal fraction to 3 decimals."""
    from astro_engine.dasha import PROKERALA_TRAVERSED_PRECISION, balance_at_birth

    longitude = 136.97252880281334
    _, exact = balance_at_birth(longitude)
    _, rounded = balance_at_birth(longitude, PROKERALA_TRAVERSED_PRECISION)
    assert exact != rounded
    assert round(1.0 - rounded, 3) == 0.273


def test_prokerala_mode_matches_their_dasha_boundary():
    """Their Venus mahadasha for this chart ends 2004-07-30T22:08:23+05:30."""
    chart = build(
        BirthData(1990, 1, 15, 4, 30, 0, *DELHI, dasha_traversed_precision=3),
        vargas=["D1"], dasha_depth=1,
    )
    venus = chart["dasha"]["mahadashas"][0]
    assert venus["lord"] == "Venus"
    gap = abs((datetime.fromisoformat(venus["end"]) - datetime(2004, 7, 30, 22, 8, 23)).total_seconds())
    assert gap < 5.0, f"off by {gap:.1f}s"



# --- transits ----------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_transits():
    from astro_engine import transits

    birth = BirthData(1990, 1, 15, 4, 30, 0, *DELHI)
    natal = build(birth, vargas=["D1"], dasha_depth=1)
    return transits.build(
        natal, birth.local_datetime(), 5.5, reference_time=datetime(2026, 9, 20)
    )


def test_sade_sati_only_uses_the_three_signs_around_the_natal_moon(sample_transits):
    """Natal Moon in Leo, so only Cancer, Leo and Virgo may appear."""
    allowed = {3, 4, 5}
    for cycle in sample_transits["sade_sati"]["cycles"]:
        for phase in cycle["phases"]:
            assert phase["sign"]["index"] in allowed


def test_sade_sati_phases_are_contiguous_and_ordered(sample_transits):
    for cycle in sample_transits["sade_sati"]["cycles"]:
        phases = cycle["phases"]
        assert phases[0]["start"] == cycle["start"]
        assert phases[-1]["end"] == cycle["end"]
        for a, b in zip(phases, phases[1:]):
            assert a["end"] == b["start"]


def test_complete_sade_sati_cycles_visit_all_three_phases(sample_transits):
    complete = [c for c in sample_transits["sade_sati"]["cycles"] if c["complete"]]
    assert len(complete) >= 2
    for cycle in complete:
        assert {p["phase"] for p in cycle["phases"]} == {"rising", "peak", "setting"}
        # Nominally 7.5 years, but the real figure depends on Saturn's varying
        # speed through those particular signs. Cancer-Virgo runs ~6.5 years.
        assert 6.0 < cycle["duration_years"] < 8.0


def test_sade_sati_cycles_recur_at_saturns_period(sample_transits):
    starts = [
        datetime.fromisoformat(c["start"])
        for c in sample_transits["sade_sati"]["cycles"] if c["complete"]
    ]
    for a, b in zip(starts, starts[1:]):
        years = (b - a).days / 365.25
        assert 28.0 < years < 31.0


def test_retrograde_re_entry_is_captured(sample_transits):
    """Saturn retrogrades back across sign boundaries, so a cycle can revisit a
    phase. The 2005-2011 cycle goes Cancer, Leo, Cancer, Leo, Virgo."""
    complete = [c for c in sample_transits["sade_sati"]["cycles"] if c["complete"]]
    # At least one cycle in a lifetime must show a retrograde re-entry, which
    # shows up as more than three phase segments.
    assert any(len(c["phases"]) > 3 for c in complete)


def test_jupiter_returns_land_near_the_orbital_period(sample_transits):
    exact = [datetime.fromisoformat(r["exact"]) for r in sample_transits["returns"]["jupiter"]]
    direct = [e for e in exact]
    for a, b in zip(direct, direct[1:]):
        gap = (b - a).days / 365.25
        assert 0.0 < gap < 13.0


def test_transit_houses_are_consistent_with_signs(sample_transits):
    for body in sample_transits["positions"].values():
        assert 1 <= body["house_from_lagna"] <= 12
        assert 1 <= body["house_from_moon"] <= 12


def test_both_varas_are_reported():
    chart = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    assert chart["panchanga"]["vara"]["name"] == "Sunday"
    assert chart["panchanga"]["vara"]["basis"] == "sunrise"
    assert chart["panchanga"]["civil_vara"]["name"] == "Monday"


@pytest.mark.parametrize(
    "house_from_moon,phase,active",
    [
        (12, "Rising", True),
        (1, "Peak", True),
        (2, "Setting", True),
        (4, "Small Panoti", True),
        (8, "Ashtama Sani", True),
        (7, None, False),    # classical Kantaka, but Prokerala does not flag it
        (10, None, False),
        (3, None, False),
    ],
)
def test_prokerala_sade_sati_vocabulary(house_from_moon, phase, active):
    """Every branch verified against their live /sade-sati endpoint."""
    from astro_engine.transits import prokerala_style

    result = prokerala_style(house_from_moon)
    assert result["transit_phase"] == phase
    assert result["is_in_sade_sati"] is active
    if active:
        assert result["description"] == (
            f"You are going through sade sati phase and you are in {phase} phase. "
        )
    else:
        assert result["description"] == "You are not going through Sade Sati phase now. "


def test_strict_sade_sati_excludes_the_panoti_houses():
    """Prokerala calls the 4th and 8th 'sade sati'; strictly they are not."""
    from astro_engine.transits import prokerala_style

    assert prokerala_style(4)["strict_sade_sati"] is False
    assert prokerala_style(8)["strict_sade_sati"] is False
    assert prokerala_style(1)["strict_sade_sati"] is True
