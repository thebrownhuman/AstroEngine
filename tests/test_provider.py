"""Provider tests.

These guard the properties the application depends on: a stored chart must be
reproducible, self-describing, and detectably stale after an engine change.
"""

from datetime import datetime

import pytest

from astro_engine import places
from astro_engine.chart import ENGINE_VERSION
from astro_engine.provider import (
    SCHEMA_VERSION, BirthDetails, ChartRecord, Conventions, LocalEngine,
    fingerprint, get_chart_summary, get_planet_details,
)

REFERENCE = datetime(2026, 9, 20)

needs_places = pytest.mark.skipif(
    not places.INDEX_PATH.exists(),
    reason="place index not built; run python -m astro_engine.places build",
)


@pytest.fixture(scope="module")
def record():
    return LocalEngine().compute(
        BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30",
                     latitude=28.6139, longitude=77.2090, full_name="Ada Lovelace"),
        reference_time=REFERENCE,
    )


# --- durability --------------------------------------------------------------

def test_record_is_self_describing(record):
    assert record.schema_version == SCHEMA_VERSION
    assert record.engine_version == ENGINE_VERSION
    assert record.provider == "astro_engine.local"
    assert record.computed_at.endswith("+00:00")


def test_record_survives_a_json_round_trip(record):
    restored = ChartRecord.from_json(record.to_json())
    assert restored.as_dict() == record.as_dict()


def test_json_is_stable_across_serialisations(record):
    """Postgres jsonb comparisons and hashes depend on this."""
    assert record.to_json() == record.to_json()


def test_same_inputs_give_the_same_hash():
    birth = BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30",
                         latitude=28.6139, longitude=77.2090)
    first = LocalEngine().compute(birth, reference_time=REFERENCE)
    second = LocalEngine().compute(birth, reference_time=REFERENCE)
    assert first.inputs_hash == second.inputs_hash
    assert first.chart == second.chart


def test_conventions_change_the_hash():
    """The same birth under a different ayanamsa is a different chart."""
    birth = BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30",
                         latitude=28.6139, longitude=77.2090)
    lahiri = LocalEngine().compute(birth, Conventions(), reference_time=REFERENCE)
    raman = LocalEngine().compute(
        birth, Conventions(ayanamsa="raman"), reference_time=REFERENCE
    )
    assert lahiri.inputs_hash != raman.inputs_hash
    assert lahiri.chart["grahas"]["Sun"]["longitude"] != \
        raman.chart["grahas"]["Sun"]["longitude"]


def test_hash_covers_both_inputs_and_conventions():
    a = fingerprint({"x": 1}, {"ayanamsa": "lahiri"})
    b = fingerprint({"x": 1}, {"ayanamsa": "raman"})
    c = fingerprint({"x": 2}, {"ayanamsa": "lahiri"})
    assert len({a, b, c}) == 3


def test_stale_detection_flags_an_old_schema(record):
    assert record.is_stale() is False
    old = ChartRecord.from_json(record.to_json())
    old.schema_version = SCHEMA_VERSION - 1
    assert old.is_stale() is True


# --- conventions -------------------------------------------------------------

def test_prokerala_mode_sets_every_matching_convention():
    resolved = Conventions(prokerala_compatible=True).resolved()
    assert resolved.equinox == "mean"
    assert resolved.sunrise_convention == "geometric"
    assert resolved.dasha_year_length == 365.25
    assert resolved.dasha_traversed_precision == 3


def test_default_conventions_are_the_correct_ones():
    default = Conventions().resolved()
    assert default.sunrise_convention == "apparent"
    assert default.dasha_traversed_precision is None


def test_prokerala_mode_changes_the_dasha_boundary():
    birth = BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30",
                         latitude=28.6139, longitude=77.2090)
    exact = LocalEngine().compute(birth, Conventions(), reference_time=REFERENCE)
    compat = LocalEngine().compute(
        birth, Conventions(prokerala_compatible=True), reference_time=REFERENCE
    )
    assert (exact.chart["dasha"]["mahadashas"][0]["end"]
            != compat.chart["dasha"]["mahadashas"][0]["end"])


# --- warnings ----------------------------------------------------------------

def test_pre_sunrise_birth_is_warned_about(record):
    assert any("before sunrise" in w for w in record.warnings)


def test_daytime_birth_has_no_sunrise_warning():
    day = LocalEngine().compute(
        BirthDetails(date_of_birth="1990-01-15", time_of_birth="14:00",
                     latitude=28.6139, longitude=77.2090),
        reference_time=REFERENCE,
    )
    assert not any("before sunrise" in w for w in day.warnings)


@needs_places
def test_obscure_place_is_flagged():
    found = LocalEngine().compute(
        BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30",
                     place="Puneduhalli"),
        reference_time=REFERENCE,
    )
    assert any("small settlement" in w for w in found.warnings)


def test_missing_location_is_rejected():
    with pytest.raises(ValueError, match="latitude and longitude"):
        LocalEngine().compute(
            BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30")
        )


@needs_places
def test_place_name_is_resolved_and_recorded():
    found = LocalEngine().compute(
        BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30", place="Delhi"),
        reference_time=REFERENCE,
    )
    assert found.resolved_place["label"] == "Delhi, India"
    assert found.chart["input"]["timezone"] == "Asia/Kolkata"


# --- read helpers ------------------------------------------------------------

def test_planet_details_are_complete(record):
    details = get_planet_details(record, "Saturn")
    for key in ("sign", "degree", "house", "nakshatra", "dignity",
                "aspects_houses", "divisional_placements"):
        assert key in details


def test_planet_lookup_is_case_insensitive(record):
    assert get_planet_details(record, "saturn") == get_planet_details(record, "Saturn")


def test_unknown_planet_raises(record):
    with pytest.raises(KeyError, match="unknown graha"):
        get_planet_details(record, "Pluto")


def test_every_graha_is_retrievable(record):
    for name in record.chart["grahas"]:
        assert get_planet_details(record, name)["graha"] == name


def test_summary_is_small_enough_for_a_dashboard(record):
    import json

    summary = get_chart_summary(record)
    assert len(json.dumps(summary)) < len(record.to_json()) / 4
    assert summary["lagna"]["sign"] == "Scorpio"
    assert summary["moon_sign"] == "Leo"


def test_numerology_only_when_a_name_is_given():
    without = LocalEngine().compute(
        BirthDetails(date_of_birth="1990-01-15", time_of_birth="04:30",
                     latitude=28.6139, longitude=77.2090),
        reference_time=REFERENCE,
    )
    assert without.numerology is None


def test_yogas_carry_their_parity_flag(record):
    flags = {y["parity"] for g in record.yogas["yoga_details"] for y in g["yoga_list"]}
    assert "verified" in flags
    assert "unverified" in flags  # Daridra must stay honestly labelled
