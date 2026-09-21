"""Tests for the layers added on top of the birth chart.

Expected values come from the live Prokerala API and are recorded in the
validation scripts; these tests guard the invariants and the specific
reverse-engineered constants that a well-meaning edit would otherwise undo.
"""

from datetime import datetime, timedelta

import pytest

from astro_engine import (
    ashtakavarga as av, doshas, kp, matching, muhurta, porutham,
    relationships as maitri, upagraha,
)
from astro_engine.chart import BirthData, build

DELHI = (28.6139, 77.2090)


@pytest.fixture(scope="module")
def chart():
    return build(
        BirthData(1990, 1, 15, 4, 30, 0, *DELHI, sunrise_convention="geometric"),
        vargas=["D1"], dasha_depth=1,
    )


# --- ashtakavarga -------------------------------------------------------------

def test_row_totals_are_the_classical_ones(chart):
    table = av.compute(chart)["ashtakavarga"]
    for graha, expected in av.EXPECTED_TOTALS.items():
        assert table[graha]["total"] == expected


def test_sarvashtakavarga_always_totals_337(chart):
    assert av.compute(chart)["sarvashtakavarga"]["total"] == av.SARVA_TOTAL


def test_trikona_zeroes_a_whole_trine_when_one_sign_is_empty():
    assert av.trikona_shodhana([0, 1, 1, 1, 5, 1, 1, 1, 7, 1, 1, 1])[:1] == [0]
    assert av.trikona_shodhana([0, 1, 1, 1, 5, 1, 1, 1, 7, 1, 1, 1])[4] == 0


def test_trikona_subtracts_the_least_of_each_trine():
    scores = [3, 0, 0, 0, 5, 0, 0, 0, 4, 0, 0, 0]
    assert av.trikona_shodhana(scores)[0] == 0
    assert av.trikona_shodhana(scores)[4] == 2
    assert av.trikona_shodhana(scores)[8] == 1


def test_ekadhipatya_zeroes_an_equal_pair_of_empty_signs():
    """Mars in the reference chart: Taurus and Libra both hold two, both go."""
    scores = [0] * 12
    scores[1] = scores[6] = 2
    assert av.ekadhipatya_shodhana(scores, occupied=set())[1] == 0
    assert av.ekadhipatya_shodhana(scores, occupied=set())[6] == 0


def test_ekadhipatya_leaves_an_equal_pair_alone_when_one_is_occupied():
    """The tie case Prokerala caught: Saturn's Mesha kept its four."""
    scores = [0] * 12
    scores[0] = scores[7] = 4
    assert av.ekadhipatya_shodhana(scores, occupied={7})[0] == 4


def test_ekadhipatya_zeroes_a_smaller_empty_sign():
    scores = [0] * 12
    scores[2], scores[5] = 3, 1
    assert av.ekadhipatya_shodhana(scores, occupied={2})[5] == 0


def test_ekadhipatya_levels_a_larger_empty_sign_down():
    scores = [0] * 12
    scores[9], scores[10] = 2, 3
    assert av.ekadhipatya_shodhana(scores, occupied={9})[10] == 2


def test_both_signs_occupied_is_untouched():
    scores = [0] * 12
    scores[0], scores[7] = 4, 2
    assert av.ekadhipatya_shodhana(scores, occupied={0, 7})[7] == 2


# --- upagrahas ----------------------------------------------------------------

def test_the_five_sun_derived_upagrahas_follow_from_dhuma():
    values = upagraha.sun_derived(100.0)
    assert values["Vyatipata"] == pytest.approx((360.0 - values["Dhuma"]) % 360.0)
    assert values["Parivesha"] == pytest.approx((values["Vyatipata"] + 180.0) % 360.0)
    assert values["Upaketu"] == pytest.approx((100.0 - 30.0) % 360.0)


def test_part_index_counts_over_eight_not_seven():
    """Counting mod 7 is the trap: it agrees on some weekdays only."""
    assert upagraha.part_index("Kala", 5, by_night=False) == 3
    assert (upagraha.WEEKDAY_LORDS.index("Sun") - 5) % 7 == 2


def test_gulika_and_mandi_are_the_same_bphs_upagraha():
    assert upagraha.PART_POINT["Gulika"] == 0.0
    assert upagraha.PART_POINT["Mandi"] == 0.0
    for vara in range(7):
        assert (upagraha.part_index("Gulika", vara, False)
                == upagraha.part_index("Mandi", vara, False))


def test_night_uses_the_vara_four_days_on():
    for vara in range(7):
        assert (upagraha.part_index("Kala", vara, True)
                == upagraha.part_index("Kala", (vara + 4) % 7, False))


def test_every_upagraha_is_reported(chart):
    from astro_engine.ephemeris import julian_day, sun_rise_set
    from astro_engine.geo import to_utc

    moment = datetime(1990, 1, 15, 4, 30)
    utc, _ = to_utc(moment, *DELHI, None)
    jd = julian_day(utc)
    solar = sun_rise_set(jd, *DELHI, convention="geometric")
    found = upagraha.compute(jd, *DELHI, chart["grahas"]["Sun"]["longitude"],
                             chart["lagna"]["sign_index"], solar, 0)
    assert [u["name"] for u in found] == upagraha.ORDER
    assert all(0.0 <= u["longitude"] < 360.0 for u in found)


# --- relationships ------------------------------------------------------------

def test_the_nodes_give_relationships_but_never_receive_them():
    assert maitri.natural("Rahu", "Sun") == maitri.ENEMY
    assert maitri.natural("Sun", "Rahu") == maitri.NO_RELATION


def test_the_lagna_has_no_natural_relationship_but_does_have_a_temporal_one(chart):
    tables = maitri.compute(chart)
    natural = {(e["first_planet"]["name"], e["second_planet"]["name"]): e["relationship"]
               for e in tables["natural_relationship"]}
    temporal = {(e["first_planet"]["name"], e["second_planet"]["name"]): e["relationship"]
                for e in tables["temporal_relationship"]}
    assert natural[("Sun", "Ascendant")] == maitri.NO_RELATION
    assert temporal[("Sun", "Ascendant")] in (maitri.FRIEND, maitri.ENEMY)


def test_compound_is_no_relation_wherever_natural_is(chart):
    tables = maitri.compute(chart)
    for natural, compound in zip(tables["natural_relationship"],
                                 tables["compound_relationship"]):
        if natural["relationship"] == maitri.NO_RELATION:
            assert compound["relationship"] == maitri.NO_RELATION


def test_every_ordered_pair_of_ten_bodies_is_present(chart):
    for table in maitri.compute(chart).values():
        assert len(table) == 100


# --- doshas -------------------------------------------------------------------

def test_kaal_sarpa_names_are_prokeralas_spellings():
    assert doshas.KAAL_SARPA_TYPES[2] == "Vaasuki"
    assert doshas.KAAL_SARPA_TYPES[9] == "Paatak"
    assert doshas.KAAL_SARPA_TYPES[11] == "Sheshnaag"
    assert len(doshas.KAAL_SARPA_TYPES) == 12


def test_a_chart_with_planets_on_both_sides_has_no_kaal_sarpa(chart):
    assert doshas.kaal_sarpa(chart)["has_dosha"] is False
    assert doshas.kaal_sarpa(chart)["type"] is None


def test_forward_hemming_is_sarpa_and_reverse_is_amrita():
    sarpa = build(BirthData(1980, 10, 5, 2, 0, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    amrita = build(BirthData(1985, 2, 13, 10, 0, 0, *DELHI), vargas=["D1"], dasha_depth=1)
    assert doshas.kaal_sarpa(sarpa)["dosha_type"] == doshas.KAAL_SARPA_LABEL
    assert doshas.kaal_sarpa(sarpa)["type"] == "Anant"
    assert doshas.kaal_sarpa(amrita)["dosha_type"] == doshas.KAAL_AMRITA_LABEL
    assert doshas.kaal_sarpa(amrita)["type"] is None


def test_papasamyam_scores_four_malefics_from_three_references(chart):
    blocks = doshas.papasamyam(chart)["papa_samyam"]["papa_planet"]
    assert [b["name"] for b in blocks] == list(doshas.PAPA_REFERENCES)
    for block in blocks:
        assert [p["name"] for p in block["planet_dosha"]] == \
            [name for name, _ in doshas.PAPA_PLANETS]


def test_papasamyam_totals_weight_by_reference_point(chart):
    """One point from the Lagna, half from the Moon, a quarter from Venus.

    Recovered by least squares over thirty-six charts; the weight turns out
    not to depend on which malefic carries the dosha.
    """
    block = doshas.compute(chart)["papasamyam"]
    expected = sum(
        doshas.PAPA_REFERENCE_WEIGHT[reference["name"]]
        for reference in block["papa_samyam"]["papa_planet"]
        for entry in reference["planet_dosha"] if entry["has_dosha"]
    )
    assert block["total_points"] == pytest.approx(expected)
    assert doshas.PAPA_REFERENCE_WEIGHT == {"Ascendant": 1.0, "Moon": 0.5,
                                            "Venus": 0.25}


# --- muhurta ------------------------------------------------------------------

@pytest.fixture(scope="module")
def day():
    return muhurta.compute(datetime(1990, 1, 15, 12, 0), *DELHI, 5.5)


def test_sixteen_choghadiya_eight_by_day_and_eight_by_night(day):
    assert len(day["choghadiya"]) == 16
    assert sum(c["is_day"] for c in day["choghadiya"]) == 8


def test_the_day_opens_with_the_weekday_lords_choghadiya(day):
    first = day["choghadiya"][0]
    assert first["ruler"] == muhurta.WEEKDAY_LORDS[day["vara_index"]]


def test_night_choghadiya_run_backwards_through_the_cycle(day):
    night = [c["name"] for c in day["choghadiya"] if not c["is_day"]]
    cycle = muhurta.CHOGHADIYA
    for earlier, later in zip(night, night[1:]):
        assert (cycle.index(later) - cycle.index(earlier)) % 7 == \
            muhurta.CHOGHADIYA_NIGHT_ADVANCE % 7


def test_gulika_kaal_and_the_gulika_upagraha_use_the_same_eighth():
    for vara in range(7):
        assert muhurta.GULIKA_KAAL[vara] == upagraha.part_index("Gulika", vara, False)


def test_abhijit_straddles_midday(day):
    abhijit = next(m for m in day["auspicious"] if m["name"] == "Abhijit Muhurat")
    start = datetime.fromisoformat(abhijit["period"][0]["start"])
    end = datetime.fromisoformat(abhijit["period"][0]["end"])
    sunrise = datetime.fromisoformat(day["sunrise"])
    sunset = datetime.fromisoformat(day["sunset"])
    midday = sunrise + (sunset - sunrise) / 2
    assert start < midday < end


def test_every_weekday_has_at_least_one_dur_muhurat():
    assert all(muhurta.DUR_MUHURAT[vara] for vara in range(7))


def test_twenty_four_horas_starting_with_the_weekday_lord(day):
    assert len(day["hora"]) == 24
    assert day["hora"][0]["hora"]["name"] == muhurta.WEEKDAY_LORDS[day["vara_index"]]


def test_hora_quality_depends_on_the_weekday_not_just_the_planet():
    assert muhurta.HORA_QUALITY[0]["Sun"] == "Good"
    assert muhurta.HORA_QUALITY[5]["Sun"] == "Bad"


def test_gowri_covers_all_eight_names_each_day(day):
    names = [g["name"] for g in day["gowri_nalla_neram"] if g["is_day"]]
    assert sorted(names) == sorted(muhurta.GOWRI_IDS)


def test_disha_shool_runs_from_sunrise(day):
    assert day["disha_shool"]["start"] == day["sunrise"]


# --- matching -----------------------------------------------------------------

def _chart(moment):
    return build(BirthData(moment.year, moment.month, moment.day,
                           moment.hour, moment.minute, 0, *DELHI),
                 vargas=["D1"], dasha_depth=1)


@pytest.fixture(scope="module")
def milan():
    return matching.compute(_chart(datetime(1990, 1, 15, 4, 30)),
                            _chart(datetime(1992, 6, 3, 11, 15)))


def test_guna_milan_totals_its_parts(milan):
    assert milan["guna_milan"]["total_points"] == \
        sum(g["obtained_points"] for g in milan["guna_milan"]["guna"])


def test_the_eight_koots_weigh_one_to_eight(milan):
    assert [g["maximum_points"] for g in milan["guna_milan"]["guna"]] == \
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    assert sum(g["maximum_points"] for g in milan["guna_milan"]["guna"]) == \
        matching.MAXIMUM_POINTS


def test_same_nadi_costs_all_eight_points():
    assert matching.nadi(0, 5)[2] == 0.0      # both Adi
    assert matching.nadi(0, 1)[2] == 8.0


def test_bhakoot_dosha_is_the_two_twelve_and_six_eight_relations():
    assert matching.bhakoot(0, 1)[2] == 0.0   # 2 and 12
    assert matching.bhakoot(0, 5)[2] == 0.0   # 6 and 8
    assert matching.bhakoot(0, 6)[2] == 7.0   # opposite signs are fine


def test_the_corrected_vasya_cells_stay_corrected():
    """Three cells the published matrices get wrong for Prokerala."""
    assert matching.VASYA_POINTS["Manava"]["Jalachara"] == 0.5
    assert matching.VASYA_POINTS["Manava"]["Chatushpada"] == 1.0
    assert matching.VASYA_POINTS["Vanachara"]["Chatushpada"] == 0.0


def test_the_corrected_gana_cells_stay_corrected():
    assert matching.GANA_POINTS["Devata"]["Manushya"] == 6.0
    assert matching.GANA_POINTS["Rakshasa"]["Devata"] == 1.0


def test_yoni_is_reported_in_prokeralas_sanskrit():
    assert matching.yoni(0, 0)[0] == "Ashwa"
    assert matching.YONI_SANSKRIT["Tiger"] == "Vyagrah"


def test_tara_koot_reports_the_nakshatra_not_the_tara():
    boy, girl, _ = matching.tara(0, 13)
    assert (boy, girl) == ("Ashwini", "Chitra")
    assert matching.tara_names(0, 13)[0] in matching.TARA_NAMES


# --- porutham -----------------------------------------------------------------

def test_all_twelve_poruthams_are_verified():
    result = porutham.compute(0, 1, 13, 2, twelve=True)
    assert {m["parity"] for m in result["matches"]} == {"verified"}
    assert result["verified_points"] == result["obtained_points"]
    assert result["verified_maximum"] == 12


def test_prokerala_counts_the_pada_from_one():
    """Their sign for a nakshatra pada is one pada further along than ours.

    This is why Rasi, Rasi Lord, Vashya and Varna looked like they were not
    sign rules at all: on our sign they are not, on theirs they are exact.
    """
    # Chitra pada 2 is the case that exposed it: same sign as pada 1 for us,
    # the next sign for them.
    assert porutham.rasi_of(13, 1) == porutham.rasi_of(13, 2) == 5
    assert porutham.prokerala_rasi_of(13, 1) == 5
    assert porutham.prokerala_rasi_of(13, 2) == 6
    # The offset is exactly one pada, everywhere.
    for nakshatra in range(27):
        for pada in (1, 2, 3, 4):
            shifted = porutham.rasi_of(nakshatra, pada + 1) if pada < 4 else None
            if shifted is not None:
                assert porutham.prokerala_rasi_of(nakshatra, pada) == shifted


def test_rasi_lord_rejects_only_three_lord_pairs():
    """The classical rule rejects far more and gets 104 of 144 cells."""
    assert porutham.RASI_LORD_ENEMIES == frozenset({
        frozenset({"Sun", "Saturn"}),
        frozenset({"Sun", "Venus"}),
        frozenset({"Moon", "Mercury"}),
    })
    # Leo is the Sun's, Capricorn is Saturn's -- mutual enemies, so it fails.
    assert porutham.rasi_lord(9, 4) is False
    assert porutham.rasi_lord(4, 9) is False
    # Aries and Taurus: Mars and Venus, not on the list.
    assert porutham.rasi_lord(1, 0) is True


def test_the_sign_tables_cover_every_sign_pair():
    for table in (porutham.RASI_TABLE, porutham.VASHYA_TABLE):
        assert len(table) == 12
        assert all(len(row) == 12 for row in table)
        assert all(cell in "01" for row in table for cell in row)
    # Vashya came back symmetric in bride and groom.
    assert all(porutham.VASHYA_TABLE[a][b] == porutham.VASHYA_TABLE[b][a]
               for a in range(12) for b in range(12))


def test_rajju_is_two_bands_not_five_body_parts():
    """Only every third star can clash, and only inside its own band."""
    assert porutham.RAJJU_BANDS == {1: [1, 7, 13, 19, 25], 4: [4, 10, 16, 22]}
    assert porutham.rajju(7, 1) is False          # both in the first band
    assert porutham.rajju(10, 4) is False         # both in the second
    assert porutham.rajju(4, 1) is True           # different bands
    assert porutham.rajju(0, 0) is True           # unbanded, even with itself
    assert porutham.rajju(1, 1) is False          # banded, against itself


def test_nadi_bands_are_not_a_partition():
    """Mula is in no band and Purva Ashadha in two -- measured, not assumed."""
    assert porutham.NADI_PORUTHAM_BANDS[18] == frozenset()
    assert porutham.NADI_PORUTHAM_BANDS[19] == frozenset({"Adi", "Madhya"})
    assert porutham.nadi(18, 0) is True           # Mula clashes with nobody
    assert porutham.nadi(19, 0) is False          # Purva Ashadha with Adi
    assert porutham.nadi(19, 1) is False          # and with Madhya


def test_gana_porutham_is_not_the_koot_behind_a_threshold():
    """A Rakshasa groom and a Manushya bride pass here and score zero there."""
    from astro_engine.matching import GANA_POINTS

    assert GANA_POINTS["Rakshasa"]["Manushya"] == 0.0
    assert ("Rakshasa", "Manushya") not in porutham.GANA_PORUTHAM_FAILS
    assert porutham.GANA_PORUTHAM_FAILS == frozenset({
        ("Devata", "Rakshasa"), ("Manushya", "Rakshasa"), ("Rakshasa", "Devata")})


def test_stree_deergha_starts_at_nine():
    assert porutham.stree_deergha(8, 0) is True      # count 9
    assert porutham.stree_deergha(7, 0) is False     # count 8


def test_veda_makes_chitra_a_triple_not_a_pair():
    assert porutham.veda(13, 4) is False
    assert porutham.veda(13, 22) is False
    assert porutham.veda(4, 22) is False
    assert porutham.veda(13, 0) is True


def test_yoni_porutham_only_fails_on_permanent_enmity():
    assert porutham.yoni(12, 0) is False     # Hasta buffalo vs Ashwini horse
    assert porutham.yoni(24, 0) is True      # ordinary enmity still passes


def test_dina_keeps_the_even_remainders():
    assert porutham.dina(1, 0) is True       # count 2
    assert porutham.dina(0, 0) is False      # count 1


def test_nakshatra_pada_maps_to_the_right_sign():
    assert porutham.rasi_of(0, 1) == 0       # Ashwini pada 1 is Mesha
    assert porutham.rasi_of(2, 3) == 1       # Krithika pada 3 is Vrishabha
    assert porutham.rasi_of(26, 4) == 11     # Revati pada 4 is Meena


# --- kp -----------------------------------------------------------------------

def test_the_nine_subs_of_a_nakshatra_fill_it_exactly():
    total = sum(fraction for _, fraction in kp.SUB_FRACTIONS)
    assert total == pytest.approx(1.0)


def test_sub_lords_start_with_the_star_lord():
    for nakshatra in range(27):
        start = nakshatra * kp.NAKSHATRA_ARC
        block = kp.lords_of(start + 1e-9)
        assert block["sub_lord"] == block["nakshatra_lord"]


def test_sub_sub_lord_starts_with_the_sub_lord():
    block = kp.lords_of(0.0)
    assert block["sub_sub_lord"] == block["sub_lord"] == block["nakshatra_lord"]


def test_kp_houses_run_cusp_to_cusp(chart):
    cusps = chart["cusps"][:12]
    found = kp.compute(chart, cusps)
    assert len(found["houses"]) == 12
    for index, house in enumerate(found["houses"]):
        assert house["start_cusp"]["longitude"] == pytest.approx(cusps[index] % 360.0)


def test_every_planet_lands_in_exactly_one_kp_house(chart):
    cusps = chart["cusps"][:12]
    for name in kp.BODIES:
        house = kp.house_of(chart["grahas"][name]["longitude"], cusps)
        assert 1 <= house <= 12


def test_significators_name_the_cusp_owner(chart):
    for block in kp.compute(chart, chart["cusps"][:12])["house_significators"]:
        assert block["cusp_owner"]["name"] in kp.BODIES


# --- the chart carries it all -------------------------------------------------

def test_optional_blocks_are_absent_unless_asked_for():
    plain = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI),
                  vargas=["D1"], dasha_depth=1)
    for key in ("ashtakavarga", "upagrahas", "planet_relationship", "doshas"):
        assert key not in plain


def test_every_optional_block_can_be_switched_on():
    full = build(BirthData(1990, 1, 15, 4, 30, 0, *DELHI),
                 vargas=["D1"], dasha_depth=1, include_ashtakavarga=True,
                 include_upagrahas=True, include_relationships=True,
                 include_doshas=True)
    for key in ("ashtakavarga", "sarvashtakavarga", "upagrahas",
                "planet_relationship", "doshas", "cusps"):
        assert key in full


def test_muhurta_belongs_to_a_date_not_to_a_birth_instant():
    """A 04:30 birth gets the coming day's periods, as Prokerala does."""
    before_sunrise = muhurta.compute(datetime(1990, 1, 15, 4, 30), *DELHI, 5.5)
    midday = muhurta.compute(datetime(1990, 1, 15, 12, 0), *DELHI, 5.5)
    assert before_sunrise["sunrise"] == midday["sunrise"]
    assert before_sunrise["vara_index"] == midday["vara_index"]


def test_choghadiya_slices_tile_the_day_without_gaps(day):
    daylight = [c for c in day["choghadiya"] if c["is_day"]]
    for earlier, later in zip(daylight, daylight[1:]):
        assert earlier["end"] == later["start"]
    assert daylight[0]["start"] == day["sunrise"]
    assert daylight[-1]["end"] == day["sunset"]


def test_a_day_of_periods_is_deterministic():
    first = muhurta.compute(datetime(1990, 1, 15, 12, 0), *DELHI, 5.5)
    second = muhurta.compute(datetime(1990, 1, 15, 12, 0), *DELHI, 5.5)
    assert first == second


def test_periods_move_with_the_season():
    winter = muhurta.compute(datetime(1990, 1, 15, 12, 0), *DELHI, 5.5)
    summer = muhurta.compute(datetime(1990, 7, 15, 12, 0), *DELHI, 5.5)
    winter_day = (datetime.fromisoformat(winter["sunset"])
                  - datetime.fromisoformat(winter["sunrise"]))
    summer_day = (datetime.fromisoformat(summer["sunset"])
                  - datetime.fromisoformat(summer["sunrise"]))
    assert summer_day - winter_day > timedelta(hours=1)


# --- ayana, ritu, sudarshana --------------------------------------------------

def test_uttarayana_covers_makara_through_mithuna():
    from astro_engine import calendar_points as cal

    for sign in (9, 10, 11, 0, 1, 2):
        assert cal.ayana(sign)["vedic_name"] == "Uttarayan"
    for sign in (3, 4, 5, 6, 7, 8):
        assert cal.ayana(sign)["vedic_name"] == "Dakshinayan"


def test_drik_ritu_pairs_solar_months_from_meena():
    from astro_engine import calendar_points as cal

    assert cal.drik_ritu(11)["vedic_name"] == "Vasant"     # Meena
    assert cal.drik_ritu(0)["vedic_name"] == "Vasant"      # Mesha
    assert cal.drik_ritu(9)["vedic_name"] == "Shishir"     # Makara
    assert len({cal.drik_ritu(s)["vedic_name"] for s in range(12)}) == 6


def test_sudarshana_reads_the_chart_from_three_references(chart):
    from astro_engine import calendar_points as cal

    wheels = cal.sudarshana_chakra(chart)
    assert set(wheels) == set(cal.SUDARSHANA_REFERENCES)
    for wheel in wheels.values():
        assert len(wheel["houses"]) == 12
        assert wheel["houses"][0]["rasi"] == wheel["reference_rasi"]


def test_every_graha_appears_once_in_each_sudarshana_wheel(chart):
    from astro_engine import calendar_points as cal

    for wheel in cal.sudarshana_chakra(chart).values():
        placed = [name for house in wheel["houses"] for name in house["occupants"]]
        assert sorted(placed) == sorted(chart["grahas"])


def test_ritu_says_the_vedic_variant_is_not_reproduced(chart):
    from astro_engine import calendar_points as cal

    assert "vedic_ritu" not in cal.compute(chart)
    assert cal.compute(chart)["drik_ritu"]["parity"] == cal.RITU_PARITY


# --- tara bala, chandra bala, chandrashtama -----------------------------------

def test_the_nine_taras_cycle_every_nine_nakshatras():
    from astro_engine import bala

    for janma in range(27):
        assert bala.tara(janma, janma)[1] == "Janma"
        assert bala.tara(janma, (janma + 9) % 27)[1] == "Janma"
        assert bala.tara(janma, (janma + 1) % 27)[1] == "Sampat"


def test_four_of_the_nine_taras_are_hostile():
    from astro_engine import bala

    bad = {number for number, _, quality in bala.TARAS if quality == "Bad"}
    assert bad == bala.HOSTILE_TARAS


def test_chandra_bala_holds_in_six_of_twelve_positions():
    from astro_engine import bala

    favoured = [rasi for rasi in range(12) if bala.chandra_bala(0, rasi)]
    assert len(favoured) == 6
    assert 0 in favoured          # the natal sign itself


def test_chandrashtama_is_the_eighth_from_the_natal_moon():
    from astro_engine import bala

    assert bala.chandrashtama(0, 7) is True
    assert bala.chandrashtama(0, 6) is False
    assert sum(bala.chandrashtama(0, rasi) for rasi in range(12)) == 1


def test_a_day_of_windows_tiles_the_date():
    from astro_engine import bala

    found = bala.day(datetime(1990, 1, 17), 5.5)
    for block in ("tara_bala", "chandra_bala"):
        windows = found[block]
        assert windows
        for earlier, later in zip(windows, windows[1:]):
            assert earlier["end"] == later["start"]


def test_every_window_names_all_nine_taras():
    from astro_engine import bala

    for window in bala.day(datetime(1990, 1, 17), 5.5)["tara_bala"]:
        assert len(window["taras"]) == 9
        listed = sum(len(t["janma_nakshatras"]) for t in window["taras"])
        assert listed == 27


def test_bala_reproduces_prokerala():
    from astro_engine import bala

    assert "verified" in bala.PARITY


def test_tara_bala_window_lists_every_favourable_star():
    """Prokerala names one tara per window but lists all five good ones."""
    from astro_engine import bala

    window = bala.day(datetime(2024, 1, 3), 5.5)["tara_bala"][0]
    favourable = {n["index"] for n in window["favourable_nakshatras"]}
    index = window["transit_nakshatra"]["index"]
    assert favourable == {
        janma for janma in range(27)
        if bala.tara(janma, index)[0] not in bala.HOSTILE_TARAS
    }
    assert len(favourable) == 15


def test_every_nakshatra_has_its_reference_block():
    """Twenty-seven rows, collected one birth per nakshatra."""
    from astro_engine import provenance
    from astro_engine.constants import (
        NAKSHATRA_ATTRIBUTE_FIELDS, NAKSHATRA_ATTRIBUTES, nakshatra_attributes,
    )

    assert len(NAKSHATRA_ATTRIBUTES) == 27
    assert [NAKSHATRA_ATTRIBUTES[i]["deity"] for i in range(27)] == [
        "Ashwini Kumara", "Yama", "Agni", "Brahma", "Moon", "Siva",
        "Aditi", "Jupiter", "Rahu", "Sun", "Aryama", "Sun",
        "Viswa Karma", "Vayu", "Indra", "Mitra", "Indra", "Niruti",
        "Varuna", "Viswadeva", "Brahma", "Vishnu", "Vasu", "Varuna",
        "Ajacharana", "Ahirbudhanya", "Poosha",
    ]
    for index in range(27):
        row = nakshatra_attributes(index)
        data = {key: row[key] for key in NAKSHATRA_ATTRIBUTE_FIELDS}
        assert tuple(data) == NAKSHATRA_ATTRIBUTE_FIELDS
        assert all(str(value).strip() for value in data.values())
        # The block carries mixed authority and has to say so: the deity is
        # BPHS, the rest was transcribed from Prokerala.
        assert row["source"] == provenance.PROVIDER
        assert row["nakshatra_deity_source"]["source"] == provenance.BPHS
    assert nakshatra_attributes(0)["deity"] == "Ashwini Kumara"
    assert nakshatra_attributes(26)["symbol"] == "Fish"
    # Indexing wraps, so a pada that runs past Revati still resolves.
    assert nakshatra_attributes(27) == nakshatra_attributes(0)


def test_the_bundled_ephemeris_is_found_without_an_env_var():
    """Moshier is accurate enough to pass ordinary checks and not the parity
    sweeps, so falling back to it silently is worse than failing loudly."""
    from astro_engine import ephemeris

    if not ephemeris.BUNDLED_EPHE_PATH.is_dir():
        pytest.skip("no bundled ephe/ directory in this checkout")
    assert ephemeris.EPHEMERIS_BACKEND == "swieph"
    assert ephemeris._EPHE_PATH is not None
