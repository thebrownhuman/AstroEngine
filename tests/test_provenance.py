"""Every block that carries a rule has to say where the rule came from.

The point of these tests is not that the strings are pretty. It is that an LLM
reading this JSON can tell BPHS from a table reverse-engineered off Prokerala,
because from the numbers alone the two look identical.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from astro_engine import provenance
from astro_engine.api import app

client = TestClient(app)

BIRTH = {
    "date": "1990-01-15", "time": "04:30",
    "latitude": 28.6139, "longitude": 77.209, "timezone": "Asia/Kolkata",
    "prokerala_compatible": True,
}
DAY = {"date": "1990-01-15", "latitude": 28.6139, "longitude": 77.209,
       "timezone": "Asia/Kolkata"}


def _stamps(node):
    """Every {"source": ..., "authority": ...} pair anywhere in a response."""
    found = []
    if isinstance(node, dict):
        if "source" in node and "authority" in node:
            found.append((node["source"], node["authority"]))
        for value in node.values():
            found.extend(_stamps(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_stamps(item))
    return found


def test_the_vocabulary_is_closed():
    assert provenance.SOURCES == set(provenance.SOURCE_MEANINGS)
    with pytest.raises(ValueError):
        provenance.block("bphs-ish", "not a real source")


def test_health_publishes_the_vocabulary():
    """A consumer should be able to learn the four values in one call."""
    vocabulary = client.get("/health").json()["source_vocabulary"]
    assert set(vocabulary) == provenance.SOURCES
    assert all(text.strip() for text in vocabulary.values())


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/v1/chart", {**BIRTH, "include_yogas": True, "include_doshas": True,
                       "include_upagrahas": True, "include_nakshatra_info": True,
                       "include_ashtakavarga": True, "include_transits": True}),
        ("/v1/transits", BIRTH),
        ("/v1/ashtakavarga", BIRTH),
        ("/v1/kp", BIRTH),
        ("/v1/muhurta", DAY),
        ("/v1/bala", DAY),
        ("/v1/porutham", {"boy_nakshatra": 3, "boy_nakshatra_pada": 1,
                          "girl_nakshatra": 7, "girl_nakshatra_pada": 2,
                          "twelve": True}),
        ("/v1/numerology", {"first_name": "John", "last_name": "Doe",
                            "date_of_birth": "2004-02-12"}),
    ],
)
def test_every_stamp_uses_a_known_source(path, payload):
    stamps = _stamps(client.post(path, json=payload).json())
    assert stamps, f"{path} carries no provenance at all"
    for source, authority in stamps:
        assert source in provenance.SOURCES, f"{path} emitted {source!r}"
        assert authority.strip(), f"{path} has a {source} stamp with no authority"


def test_the_blocks_without_textual_authority_say_so():
    """These are the ones it would be wrong to present as scripture."""
    chart = client.post("/v1/chart", json={
        **BIRTH, "include_doshas": True, "include_upagrahas": True,
        "include_nakshatra_info": True,
    }).json()

    # Kaal Sarpa is the modern rule. BPHS's Sarpa Yoga is a different construct
    # -- malefics in kendras -- so this must not claim BPHS.
    assert chart["doshas"]["kaal_sarpa"]["source"] == provenance.PROVIDER

    upagrahas = {u["name"]: u["source"] for u in chart["upagrahas"]}
    assert upagrahas["Dhuma"] == provenance.CLASSICAL
    # The part index behind the time-derived six was measured, not read.
    for name in ("Gulika", "Mandi", "Kala", "Mrityu", "Ardha Prahara", "Yamaghanta"):
        assert upagrahas[name] == provenance.PROVIDER, name

    # The block is split in authority and has to carry both stamps.
    info = chart["nakshatra_info"]
    assert info["source"] == provenance.PROVIDER
    assert info["nakshatra_deity_source"]["source"] == provenance.BPHS

    muhurta = client.post("/v1/muhurta", json=DAY).json()
    assert muhurta["source"] == provenance.PROVIDER
    assert muhurta["gowri_nalla_neram_source"]["source"] == provenance.PROVIDER


def test_daridra_stays_unverified():
    """No rule was ever found. It must not drift into looking verified."""
    chart = client.post("/v1/chart", json={**BIRTH, "include_yogas": True}).json()
    yogas = {y["name"]: y
             for group in chart["yogas"]["yoga_details"]
             for y in group["yoga_list"]}

    daridra = yogas["Daridra Yoga"]
    assert daridra["source"] == provenance.UNVERIFIED
    assert daridra["parity"] == "unverified"
    # Any other yoga carries the ordinary stamp, so the unverified one stands out.
    assert yogas["Hamsa Yoga"]["source"] == provenance.CLASSICAL


def test_bphs_derived_chart_blocks_are_labelled():
    """`sources` is not uniformly BPHS, and must not be read as though it were."""
    sources = client.post("/v1/chart", json=BIRTH).json()["sources"]

    expected = {
        "graha_nature": provenance.BPHS,
        "graha_drishti": provenance.BPHS,
        "rashi_drishti": provenance.BPHS,
        "vargas": provenance.BPHS,
        "dasha": provenance.BPHS,
        "dignity": provenance.BPHS,
        # Panchanga is standard practice, and the house significations are an
        # editorial summary rather than a quotation. Neither is BPHS.
        "panchanga": provenance.CLASSICAL,
        "house_significations": provenance.CLASSICAL,
    }
    assert {key: block["source"] for key, block in sources.items()} == expected
    assert "Chapter 26" in sources["graha_drishti"]["authority"]
    assert "Chapter 6" in sources["vargas"]["authority"]


def test_ashtakavarga_splits_the_reduction_out():
    """The bindu tables are BPHS 66; the ekadhipatya tie rule was measured."""
    chart = client.post("/v1/chart", json={
        **BIRTH, "include_ashtakavarga": True,
    }).json()

    assert chart["ashtakavarga_source"]["source"] == provenance.BPHS
    assert "66" in chart["ashtakavarga_source"]["authority"]
    for graha, table in chart["ashtakavarga"].items():
        assert table["ekaadhipatya"]["source"] == provenance.PROVIDER, graha

    # The stamp is a sibling because the block is keyed by graha name; a
    # consumer iterating it must not find "source" sitting among the grahas.
    assert "source" not in chart["ashtakavarga"]


def test_gochara_is_not_claimed_as_bphs():
    chart = client.post("/v1/chart", json={**BIRTH, "include_transits": True}).json()
    assert chart["transits_source"]["source"] == provenance.CLASSICAL
    assert client.post("/v1/transits", json=BIRTH).json()["source"] == provenance.CLASSICAL


def test_all_twelve_porutham_checks_are_verified():
    """The docstring claimed six for a long time after all twelve were measured."""
    report = client.post("/v1/porutham", json={
        "boy_nakshatra": 3, "boy_nakshatra_pada": 1,
        "girl_nakshatra": 7, "girl_nakshatra_pada": 2, "twelve": True,
    }).json()
    assert report["verified_maximum"] == 12
    assert report["verified_points"] == report["obtained_points"]
    assert {m["parity"] for m in report["matches"]} == {"verified"}
    # Verified against Prokerala, but still without textual authority.
    assert report["source"] == provenance.PROVIDER


# Blocks with no rule to attribute: raw astronomy, echoes of the request, or
# pure geometry. Each needs a reason, so that adding to this set is a decision
# rather than the easy way past the test below.
NO_RULE = {
    "engine": "settings and versions, not a rule",
    "input": "the resolved request, echoed back",
    "lagna": "an ephemeris longitude",
    "midheaven": "an ephemeris longitude",
    "cusps": "Placidus cusps; not Vedic, present only for KP",
    "grahas": "ephemeris longitudes; the rules over them are stamped in `sources`",
    "houses": "whole-sign arithmetic; significations stamped in `sources`",
    "aspects": "stamped as graha_drishti in `sources`",
    "rashi_aspects": "stamped as rashi_drishti in `sources`",
    "solar_day": "sunrise and sunset times; the convention is named in the block",
    "sources": "the stamps themselves",
    "vargas": "stamped in `sources`; the map is keyed D1/D9/...",
    "dasha": "stamped in `sources`; the map is keyed by lord",
    "current_dasha": "a view onto `dasha`, which is stamped in `sources`",
    "panchanga": "stamped in `sources`",
    "ashtakavarga": "stamped by the `ashtakavarga_source` sibling",
    "transits": "stamped by the `transits_source` sibling",
    "planet_relationship": "stamped by the `planet_relationship_source` sibling",
    "solstice": "stamped by the `calendar_source` sibling",
    "drik_ritu": "stamped by the `calendar_source` sibling",
    "sudarshana_chakra": "stamped by the `calendar_source` sibling",
}

EVERYTHING = {
    **BIRTH,
    "include_yogas": True, "include_transits": True, "include_ashtakavarga": True,
    "include_upagrahas": True, "include_relationships": True,
    "include_doshas": True, "include_calendar": True,
    "include_nakshatra_info": True,
}


def _carries_a_stamp(node):
    if isinstance(node, dict):
        if "source" in node and "authority" in node:
            return True
        return any(_carries_a_stamp(v) for v in node.values())
    if isinstance(node, list):
        return any(_carries_a_stamp(item) for item in node)
    return False


def test_no_chart_block_is_silently_unattributed():
    """The check that stops this drifting.

    Enumerating the blocks by hand is how a new one ships unstamped: it is not
    that anybody decides to omit it, it is that nobody remembers it exists. A
    block added from here on either carries a stamp, or its name has to be
    added to NO_RULE with a reason, which is a decision somebody makes.
    """
    chart = client.post("/v1/chart", json=EVERYTHING).json()

    unattributed = [
        key for key in chart
        if not key.endswith("_source")
        and key not in NO_RULE
        and not _carries_a_stamp(chart[key])
    ]
    assert not unattributed, (
        f"blocks with no provenance: {sorted(unattributed)}. Stamp them, or add "
        f"them to NO_RULE with the reason they carry no rule."
    )


def test_the_no_rule_list_has_not_gone_stale():
    """An entry that no longer matches a real block is a stale excuse."""
    chart = client.post("/v1/chart", json=EVERYTHING).json()
    assert not (set(NO_RULE) - set(chart)), (
        f"NO_RULE names blocks the chart no longer has: "
        f"{sorted(set(NO_RULE) - set(chart))}"
    )
    assert all(reason.strip() for reason in NO_RULE.values())


def test_dasha_says_which_conventions_produced_it():
    """The most-consumed block, and mixed authority in the misleading direction."""
    stamp = client.post("/v1/chart", json=BIRTH).json()["sources"]["dasha"]
    assert stamp["source"] == provenance.BPHS
    # The scheme is BPHS; the two settings that move boundaries are not, and
    # the authority string has to say so rather than implying the dates are
    # scriptural.
    assert "Chapter 46" in stamp["authority"]
    assert "365.25" in stamp["authority"]
    assert "three decimals" in stamp["authority"]


def test_ekadhipatya_diverges_from_bphs_on_purpose():
    """BPHS Chapter 68 is explicit here, and this engine does not follow it.

    Its worked example gives Capricorn and Aquarius the same trikona-corrected
    number 2; Capricorn holds planets, Aquarius does not, and the text reduces
    Aquarius to zero. This engine leaves the empty sign alone on an exact tie,
    because that is what Prokerala does and what the 204/204 measured checks
    require.

    The test exists so nobody "corrects" this to match the book without
    realising it breaks parity. If you do change it, the ashtakavarga sweep
    will fail, and that is the intended alarm.
    """
    from astro_engine.ashtakavarga import ekadhipatya_shodhana

    scores = [0] * 12
    scores[9] = 2   # Capricorn, occupied
    scores[10] = 2  # Aquarius, empty, same number
    out = ekadhipatya_shodhana(scores, occupied={9})

    assert out[9] == 2, "the occupied sign is untouched either way"
    assert out[10] == 2, "Prokerala's reading: an exact tie is left alone"
    # BPHS Chapter 68 would give 0 here. That divergence has to stay visible
    # in the stamp rather than being quietly absorbed.
    stamp = client.post("/v1/chart", json={
        **BIRTH, "include_ashtakavarga": True,
    }).json()["ashtakavarga"]["Sun"]["ekaadhipatya"]
    assert stamp["source"] == provenance.PROVIDER
    assert "Chapter 68" in stamp["authority"]
