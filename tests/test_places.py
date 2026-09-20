"""Place lookup tests.

The coordinates asserted here are the well-known locations of these towns. They
exist because GeoNames ranking is genuinely tricky for Indian birth places:
districts, tehsils and villages frequently share a name, and the obvious
ranking rules each get at least one of these cases wrong.
"""

import pytest

from astro_engine import places

pytestmark = pytest.mark.skipif(
    not places.INDEX_PATH.exists(),
    reason="place index not built; run python -m astro_engine.places build",
)

# name -> (latitude, longitude) of the place a user actually means.
KNOWN = {
    "Delhi": (28.65, 77.23),
    "Mumbai": (19.07, 72.88),
    "Pune": (18.52, 73.86),
    "Bengaluru": (12.97, 77.59),
    # Uttar Pradesh towns that collide with a same-named district or tehsil.
    "Sultanpur": (26.26, 82.07),
    "Ballia": (25.76, 84.15),
    "Ghazipur": (25.58, 83.59),
    "Jaunpur": (25.75, 82.69),
    "Azamgarh": (26.07, 83.18),
    "London": (51.51, -0.13),
}


@pytest.mark.parametrize("query,expected", KNOWN.items())
def test_top_match_is_the_place_people_mean(query, expected):
    found = places.resolve(query)
    latitude, longitude = expected
    assert abs(found.latitude - latitude) < 0.15, f"{query}: got {found.latitude}"
    assert abs(found.longitude - longitude) < 0.15, f"{query}: got {found.longitude}"


def test_district_does_not_outrank_its_town():
    """Sultanpur district holds 3.8M people; the town holds 110k. The town wins."""
    found = places.resolve("Sultanpur")
    assert found.kind == "city"
    assert found.population < 1_000_000


def test_tehsil_population_reaches_the_right_town():
    """Ballia town is recorded with population 0; its tehsil has 979,400.

    The tehsil figure must land on the co-located town, not on a namesake
    village elsewhere in the state.
    """
    found = places.resolve("Ballia")
    assert found.admin1 == "Uttar Pradesh"
    assert found.population > 500_000
    assert abs(found.latitude - 25.76) < 0.1


def test_accents_are_ignored():
    assert places.resolve("Sultanpur").name == places.resolve("Sultānpur").name


def test_prefix_search_works_for_partial_typing():
    labels = [p.label for p in places.search("Bengalur")]
    assert any("Bengaluru" in label for label in labels)


def test_country_filter_narrows_results():
    assert all(p.country_code == "IN" for p in places.search("Delhi", country="IN"))
    uk = places.search("London", country="GB")
    assert uk and uk[0].country_code == "GB"


def test_every_result_carries_a_usable_timezone():
    from zoneinfo import ZoneInfo

    for query in ("Delhi", "London", "New York", "Sydney"):
        found = places.resolve(query)
        assert ZoneInfo(found.timezone) is not None


def test_unknown_place_raises():
    with pytest.raises(ValueError, match="no place found"):
        places.resolve("Xyzzy Notaplace")


def test_empty_query_returns_nothing():
    assert places.search("") == []
    assert places.search("   ") == []


def test_quotes_in_query_do_not_break_fts():
    assert places.search('Delhi" OR "x') == [] or True  # must not raise


def test_resolved_place_drives_the_chart():
    from astro_engine.chart import BirthData, build

    found = places.resolve("Delhi")
    chart = build(
        BirthData(1990, 1, 15, 4, 30, 0, found.latitude, found.longitude, found.timezone),
        vargas=["D1"], dasha_depth=1,
    )
    assert chart["input"]["timezone"] == "Asia/Kolkata"
    assert chart["lagna"]["sign_en"] == "Scorpio"
