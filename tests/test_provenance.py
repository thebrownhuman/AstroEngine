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
                       "include_upagrahas": True, "include_nakshatra_info": True}),
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
    sources = client.post("/v1/chart", json=BIRTH).json()["sources"]
    assert {block["source"] for block in sources.values()} == {provenance.BPHS}
    assert "Chapter 26" in sources["graha_drishti"]["authority"]


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
