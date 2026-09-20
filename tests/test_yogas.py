"""Yoga tests.

Expected verdicts come from Prokerala's live /astrology/yoga endpoint across 21
charts. Each rule below was either confirmed against them or is explicitly
flagged as unverified; the parity labels are asserted here so a later edit
cannot quietly upgrade an unverified rule.
"""

import pytest

from astro_engine import yogas
from astro_engine.chart import BirthData, build

DELHI = (28.6139, 77.2090)


def chart_for(year, month, day, hour, minute, latitude, longitude):
    return build(
        BirthData(year, month, day, hour, minute, 0, latitude, longitude),
        vargas=["D1"], dasha_depth=1,
    )


@pytest.fixture(scope="module")
def sample():
    return chart_for(1990, 1, 15, 4, 30, *DELHI)


# --- structure ---------------------------------------------------------------

def test_reports_all_twentyfour(sample):
    found = yogas.detect(sample)
    assert len(found) == 24
    assert len({y.name for y in found}) == 24


def test_groups_match_prokeralas_order(sample):
    report = yogas.report(sample)
    assert [g["name"] for g in report["yoga_details"]] == list(yogas.GROUP_ORDER)


def test_group_counts_agree_with_members(sample):
    for group in yogas.report(sample)["yoga_details"]:
        assert group["count"] == sum(y["has_yoga"] for y in group["yoga_list"])


def test_every_yoga_states_its_parity(sample):
    allowed = {"verified", "verified_negative_only", "unverified", "not_in_prokerala_set"}
    for yoga in yogas.detect(sample):
        assert yoga.as_dict()["parity"] in allowed


def test_parity_sets_are_disjoint_and_complete(sample):
    names = {y.name for y in yogas.detect(sample)}
    assert not (yogas.VERIFIED & yogas.WEAKLY_VERIFIED)
    assert not (yogas.VERIFIED & yogas.EXTRA)
    assert not (yogas.UNVERIFIED & yogas.VERIFIED)
    assert (yogas.VERIFIED | yogas.WEAKLY_VERIFIED
            | yogas.UNVERIFIED | yogas.EXTRA) == names


def test_daridra_is_not_claimed_as_verified():
    """It disagrees with Prokerala on 8 of 21 charts; do not pretend otherwise."""
    assert "Daridra Yoga" in yogas.UNVERIFIED
    assert "Daridra Yoga" not in yogas.VERIFIED


def test_kahala_and_kamal_are_only_weakly_verified():
    """Prokerala never reported these as present, so agreement is one-sided."""
    assert yogas.WEAKLY_VERIFIED == {"Kahala Yoga", "Kamal Yoga"}


def test_live_vocabulary_not_the_stale_spec_names(sample):
    """Their OpenAPI example says Sunafa/Kedar/Veshi; the live API says otherwise."""
    names = {y.name for y in yogas.detect(sample)}
    for live, stale in [("Sunapha Yoga", "Sunafa Yoga"), ("Kedara Yoga", "Kedar Yoga"),
                        ("Vesi Yoga", "Veshi Yoga"), ("Kahala Yoga", "Kahal Yoga"),
                        ("Anapha Yoga", "Anafa Yoga"),
                        ("Duradhara Yoga", "Durudhara Yoga"),
                        ("Ubhaya Chari Yoga", "Ubhayachari Yoga")]:
        assert live in names and stale not in names


# --- rules confirmed against Prokerala ---------------------------------------

def test_kemadruma_ignores_conjunction_with_the_moon():
    """Prokerala checks only the 2nd and 12th from the Moon.

    Including the conjunction condition cost 5 mismatches out of 15.
    """
    for entry in yogas.detect(chart_for(1965, 5, 29, 20, 17, 51.5074, -0.1278)):
        if entry.name == "Kemadruma Yoga":
            assert entry.present is True
            assert entry.evidence["with_moon"], "this chart has a graha with the Moon"
            return
    pytest.fail("Kemadruma not reported")


def test_kamal_requires_all_four_kendras_occupied():
    view = yogas.ChartView(chart_for(1965, 5, 29, 20, 17, 51.5074, -0.1278))
    houses = {view.house(g) for g in yogas.SEVEN_GRAHAS}
    entry = yogas.kamala(view)
    # All seven sit inside the kendras here, but not all four are occupied.
    assert houses <= {1, 4, 7, 10}
    assert houses != {1, 4, 7, 10}
    assert entry.present is False


def test_raja_yoga_ignores_a_lone_yogakaraka():
    view = yogas.ChartView(chart_for(1956, 3, 15, 2, 17, -33.8688, 151.2093))
    entry = yogas.raja_yoga(view)
    assert entry.present is False
    assert entry.evidence["links"] == []


def test_raja_yoga_needs_a_mutual_aspect_not_one_way():
    for entry in yogas.detect(chart_for(1990, 1, 15, 4, 30, *DELHI)):
        if entry.name == "Raja Yoga":
            for link in entry.evidence["links"]:
                assert link["type"] in ("conjunction", "mutual_aspect")
            return
    pytest.fail("Raja Yoga not reported")


# --- rule invariants ---------------------------------------------------------

def test_panchamahapurusha_needs_dignity_and_a_kendra(sample):
    view = yogas.ChartView(sample)
    for graha, name in yogas.MAHAPURUSHA.items():
        entry = yogas.mahapurusha(view, graha)
        assert entry.name == name
        expected = (view.dignified(graha) and view.house(graha) in yogas.KENDRAS)
        assert entry.present is expected


def test_durudhara_implies_both_sunapha_and_anapha(sample):
    view = yogas.ChartView(sample)
    if yogas.duradhara(view).present:
        assert yogas.sunapha(view).present and yogas.anapha(view).present


def test_ubhaya_chari_implies_both_vesi_and_vasi(sample):
    view = yogas.ChartView(sample)
    if yogas.ubhayachari(view).present:
        assert yogas.vesi(view).present and yogas.vasi(view).present


def test_kemadruma_excludes_the_other_chandra_yogas(sample):
    view = yogas.ChartView(sample)
    if yogas.kemadruma(view).present:
        assert not yogas.sunapha(view).present
        assert not yogas.anapha(view).present


def test_kemdrum_duplicates_kemadruma(sample):
    """Their list carries the same yoga twice under two spellings."""
    view = yogas.ChartView(sample)
    assert yogas.kemdrum(view).present == yogas.kemadruma(view).present


def test_kuja_yoga_is_mangal_dosha(sample):
    view = yogas.ChartView(sample)
    entry = yogas.kuja(view)
    assert entry.present is (view.house("Mars") in (1, 2, 4, 7, 8, 12))


def test_kedara_counts_signs_not_houses(sample):
    view = yogas.ChartView(sample)
    entry = yogas.kedara(view)
    assert entry.present is (len({view.sign(g) for g in yogas.SEVEN_GRAHAS}) == 4)


def test_every_detector_explains_itself(sample):
    for entry in yogas.detect(sample):
        assert entry.reason, f"{entry.name} gave no reason"
        assert isinstance(entry.evidence, dict)


def test_detection_is_deterministic(sample):
    first = yogas.report(sample)
    second = yogas.report(sample)
    assert first == second
