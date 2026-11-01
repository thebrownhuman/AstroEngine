"""The astro_rules layer: schema, condition language, firing with evidence."""

import copy
import re

import pytest
import yaml
from fastapi.testclient import TestClient

import astro_rules
from astro_rules import conditions
from astro_engine import api
from astro_engine.chart import BirthData, build


@pytest.fixture(scope="module")
def chart_1990():
    # Lagna Pisces: Jupiter (1st and 10th lord) sits in the 4th.
    return build(BirthData(1990, 1, 1, 12, 0, 0, 28.6, 77.2, "Asia/Kolkata"),
                 vargas=["D1"], dasha_depth=1, reference_time=None)


@pytest.fixture(scope="module")
def chart_saturn_12():
    # Lagna lord Saturn in the 12th, joined by Venus and aspected by Jupiter.
    return build(BirthData(1990, 2, 10, 6, 0, 0, 28.6, 77.2, "Asia/Kolkata"),
                 vargas=["D1"], dasha_depth=1)


# ------------------------------------------------------------------ the rule set

def test_all_144_house_lord_rules_present_with_unique_ids():
    rules = [r for r in astro_rules.RULES if r["id"].startswith("bphs.house_lords.")]
    assert len(rules) == 144
    assert len({r["id"] for r in rules}) == 144
    pairs = {(r["when"]["lord_of"], r["when"]["in_house"]) for r in rules}
    assert pairs == {(l, h) for l in range(1, 13) for h in range(1, 13)}


def test_every_rule_cites_its_verse_in_both_translations():
    for r in astro_rules.RULES:
        if not r["id"].startswith("bphs.house_lords."):
            continue
        lord, house = r["when"]["lord_of"], r["when"]["in_house"]
        verse = str((lord - 1) * 12 + house)
        assert r["source"] == {"book": "BPHS", "edition": "Sharma", "ch": 26, "v": verse}, r["id"]
        assert r["cross_check"] == {"book": "BPHS", "edition": "Santhanam", "ch": 24, "v": verse}
        assert r["provenance"] == "bphs"
        assert r["id"] == f"bphs.house_lords.{lord}_in_{house}"


def test_meanings_are_short_paraphrases():
    for r in astro_rules.RULES:
        assert 10 < len(r["meaning"]) <= 220, r["id"]


def test_flagged_rules_carry_both_readings():
    flagged = [r for r in astro_rules.RULES if r.get("flagged")]
    assert flagged
    for r in flagged:
        assert {v["edition"] for v in r["variants"]} == {"Sharma", "Santhanam"}


# ------------------------------------------------------------------ loader / schema

def _write(tmp_path, rules):
    (tmp_path / "x.yaml").write_text(yaml.safe_dump(rules), encoding="utf-8")
    return tmp_path


GOOD = {"id": "bphs.test.one", "when": {"lord_of": 1, "in_house": 1}, "meaning": "Some result.",
        "polarity": "positive", "domains": ["self"], "provenance": "bphs",
        "source": {"book": "BPHS", "edition": "Sharma", "ch": 26, "v": "1"}}


def test_loader_accepts_a_good_rule(tmp_path):
    assert astro_rules.load(_write(tmp_path, [GOOD]))[0]["id"] == "bphs.test.one"


@pytest.mark.parametrize("change, message", [
    ({"polarity": "great"}, "polarity"),
    ({"domains": ["astrology"]}, "domains"),
    ({"source": {"book": "BPHS", "edition": "Sharma", "ch": 26}}, "citation"),
    ({"when": {"in_house": 1}}, "need lord_of or planet"),
    ({"when": {"lord_of": 13}}, "lord_of"),
    ({"when": {"lord_of": 1, "dignity": "happy"}}, "dignity"),
    ({"when": {"lord_of": 1, "conjunct": "Pluto"}}, "target"),
    ({"when": {"lord_of": 1, "sitting_in": 2}}, "unknown keys"),
    ({"provenance": "vibes"}, "provenance"),
    ({"flagged": True}, "flagged"),
    ({"variants": [{"edition": "Sharma", "reading": "x"}]}, "flagged"),
    ({"surprise": 1}, "unknown fields"),
    ({"id": "No Spaces Allowed"}, "bad id"),
])
def test_loader_rejects_bad_rules(tmp_path, change, message):
    with pytest.raises(astro_rules.RuleError, match=message):
        astro_rules.load(_write(tmp_path, [{**GOOD, **change}]))


def test_loader_rejects_missing_fields_and_duplicates(tmp_path):
    with pytest.raises(astro_rules.RuleError, match="missing"):
        astro_rules.load(_write(tmp_path, [{k: v for k, v in GOOD.items() if k != "meaning"}]))
    with pytest.raises(astro_rules.RuleError, match="duplicate"):
        astro_rules.load(_write(tmp_path, [GOOD, GOOD]))


# ------------------------------------------------------------------ condition language

def test_conditions_read_engine_fields(chart_1990):
    c = chart_1990
    assert c["houses"][0]["lord"] == "Jupiter" and c["grahas"]["Jupiter"]["house"] == 4
    ok, ev = conditions.evaluate({"lord_of": 1, "in_house": 4}, c)
    assert ok
    assert ev == [
        {"fact": "Jupiter is lord of house 1", "field": "houses[0].lord", "value": "Jupiter"},
        {"fact": "Jupiter is in house 4", "field": "grahas.Jupiter.house", "value": 4},
    ]
    assert not conditions.evaluate({"lord_of": 1, "in_house": 5}, c)[0]
    assert conditions.evaluate({"lord_of": 1, "in_house": [3, 4]}, c)[0]
    assert conditions.evaluate({"planet": "Jupiter", "in_sign": "Gemini"}, c)[0]
    assert conditions.evaluate({"planet": "Jupiter", "in_sign": 2}, c)[0]
    assert conditions.evaluate({"planet": "Mars", "dignity": "own_sign"}, c)[0]
    assert not conditions.evaluate({"planet": "Mars", "dignity": "exalted"}, c)[0]
    assert conditions.evaluate({"planet": "Sun", "nature": "malefic"}, c)[0]
    # Sun (house 10) casts its 7th aspect on Jupiter in the 4th.
    ok, ev = conditions.evaluate({"planet": "Jupiter", "aspected_by": "Sun"}, c)
    assert ok and ev[-1]["value"] == ["Sun"]
    assert conditions.evaluate({"planet": "Jupiter", "associated_with": "malefic"}, c)[0]
    assert not conditions.evaluate({"planet": "Jupiter", "conjunct": "benefic"}, c)[0]


def test_combinators(chart_1990):
    c = chart_1990
    assert conditions.evaluate({"planet": "Jupiter", "all": [{"in_house": 4}, {"nature": "benefic"}]}, c)[0]
    assert not conditions.evaluate({"planet": "Jupiter", "all": [{"in_house": 4}, {"in_house": 5}]}, c)[0]
    assert conditions.evaluate({"planet": "Jupiter", "any": [{"in_house": 5}, {"in_house": 4}]}, c)[0]
    assert not conditions.evaluate({"planet": "Jupiter", "not": {"in_house": 4}}, c)[0]
    ok, ev = conditions.evaluate({"planet": "Jupiter", "not": {"in_house": 5}}, c)
    assert ok and ev[-1]["value"] is False


def test_yoga_and_dasha_conditions(chart_1990):
    c = copy.deepcopy(chart_1990)
    c["yogas"] = {"yoga_details": [{"yoga_list": [{"name": "Gajakesari Yoga", "has_yoga": True},
                                                  {"name": "Budha-Aditya Yoga", "has_yoga": False}]}]}
    assert conditions.evaluate({"yoga_present": "Gajakesari Yoga"}, c)[0]
    assert not conditions.evaluate({"yoga_present": "Budha-Aditya Yoga"}, c)[0]
    c["current_dasha"] = {"chain": [{"level": "mahadasha", "lord": "Jupiter"}]}
    assert conditions.evaluate({"dasha_lord": "Jupiter"}, c)[0]
    assert conditions.evaluate({"lord_of": 1, "dasha_lord": "subject"}, c)[0]
    assert not conditions.evaluate({"lord_of": 2, "dasha_lord": "subject"}, c)[0]


# ------------------------------------------------------------------ firing on known charts

def test_known_chart_fires_one_rule_per_house_lord(chart_1990):
    hits = {h["id"]: h for h in astro_rules.fired(chart_1990)}
    assert set(hits) == {
        "bphs.house_lords.1_in_4", "bphs.house_lords.2_in_9", "bphs.house_lords.3_in_11",
        "bphs.house_lords.4_in_11", "bphs.house_lords.5_in_12", "bphs.house_lords.6_in_10",
        "bphs.house_lords.7_in_11", "bphs.house_lords.8_in_11", "bphs.house_lords.9_in_9",
        "bphs.house_lords.10_in_4", "bphs.house_lords.11_in_10", "bphs.house_lords.12_in_10",
    }
    hit = hits["bphs.house_lords.9_in_9"]
    assert hit["subject"] == "Mars"
    assert [e["field"] for e in hit["evidence"]] == ["houses[8].lord", "grahas.Mars.house"]
    assert hit["source"]["v"] == "105"
    # Flagged rules travel with both readings.
    assert hits["bphs.house_lords.8_in_11"]["flagged"] is True
    assert len(hits["bphs.house_lords.8_in_11"]["variants"]) == 2


def test_known_chart_fires_conditional_clause_with_evidence():
    # Lagna lord Jupiter (a benefic) sits in the 7th.
    c = build(BirthData(1990, 2, 1, 6, 0, 0, 28.6, 77.2, "Asia/Kolkata"), vargas=["D1"], dasha_depth=1)
    assert c["grahas"][c["houses"][0]["lord"]]["house"] == 7
    hit = next(h for h in astro_rules.fired(c) if h["id"] == "bphs.house_lords.1_in_7")
    (clause,) = hit["clauses"]  # only the benefic-lord branch, not the malefic one
    assert clause["meaning"].startswith("Aimless wanderer")
    assert clause["evidence"] == [{"fact": f"{hit['subject']} is a benefic",
                                   "field": f"grahas.{hit['subject']}.bphs_nature", "value": "benefic"}]


def test_benefic_association_suppresses_negated_clause(chart_saturn_12):
    c = chart_saturn_12
    assert c["houses"][0]["lord"] == "Saturn" and c["grahas"]["Saturn"]["house"] == 12
    hit = next(h for h in astro_rules.fired(c) if h["id"] == "bphs.house_lords.1_in_12")
    assert "clauses" not in hit  # Venus joins and Jupiter aspects Saturn
    ok, ev = conditions.evaluate({"associated_with": "benefic"}, c, "Saturn")
    facts = [e["fact"] for e in ev]
    assert ok and "Saturn is conjunct Venus" in facts
    assert any(re.match(r"Saturn is aspected by .*Jupiter", f) for f in facts)


def test_unmet_clause_is_not_reported(chart_1990):
    # 8th lord Venus in the 11th: the 'joined by a benefic' clause needs a benefic in Venus's sign.
    hit = next(h for h in astro_rules.fired(chart_1990) if h["id"] == "bphs.house_lords.8_in_11")
    venus_sign = chart_1990["grahas"]["Venus"]["sign_index"]
    joined = [n for n, g in chart_1990["grahas"].items()
              if n != "Venus" and g["sign_index"] == venus_sign and g["bphs_nature"] == "benefic"]
    assert ("clauses" in hit) == bool(joined)


# ------------------------------------------------------------------ API

BODY = {"date": "1990-01-01", "time": "12:00:00",
        "latitude": 28.6, "longitude": 77.2, "timezone": "Asia/Kolkata"}


def test_rules_endpoint(monkeypatch):
    monkeypatch.delenv("ASTRO_API_KEYS", raising=False)
    c = TestClient(api.create_app())
    r = c.post("/v1/rules", json=BODY)
    assert r.status_code == 200
    out = r.json()
    assert out["rules_loaded"] == len(astro_rules.RULES)
    assert out["count"] == len(out["rules"]) == 12
    first = next(h for h in out["rules"] if h["id"] == "bphs.house_lords.1_in_4")
    assert first["evidence"][0]["value"] == "Jupiter"
    assert first["source"]["edition"] == "Sharma"


def test_rules_endpoint_needs_key(monkeypatch):
    monkeypatch.setenv("ASTRO_API_KEYS", "secret")
    try:
        c = TestClient(api.create_app())
        assert c.post("/v1/rules", json=BODY).status_code == 401
        assert c.post("/v1/rules", json=BODY, headers={"X-API-Key": "secret"}).status_code == 200
    finally:
        monkeypatch.delenv("ASTRO_API_KEYS")
        api.guard.configure()
