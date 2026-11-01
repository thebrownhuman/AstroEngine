"""Interpretation rules transcribed from the classical books, with citations.

Rules live in YAML files under ``rules/``, one file per area. They are loaded
and schema-checked when this package is imported, so a malformed rule fails
the process at start-up rather than at request time.

Each rule:

    id:          unique, "<book>.<area>.<name>"
    when:        a condition (see ``conditions``) that binds a subject graha
    meaning:     short paraphrase of the verse (never a long quotation)
    polarity:    positive | negative | mixed
    domains:     life areas the result speaks to (see DOMAINS)
    source:      {book, edition, ch, v} - the primary translation
    cross_check: {book, edition, ch, v} - the second translation read against it
    provenance:  bphs | classical | provider_compatible | unverified
    clauses:     optional [{when, meaning, polarity}] - extra results the verse
                 gives only under a further condition (e.g. "if joined a malefic")
    variants:    optional [{edition, reading}] - where the translations differ
    flagged:     true when variants exist; a reader should see both readings

``fired(chart)`` returns the rules whose ``when`` holds, each with the
evidence (engine fields and values) that made it hold.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import conditions

RULES_DIR = Path(__file__).parent / "rules"

POLARITIES = ("positive", "negative", "mixed")
PROVENANCES = ("bphs", "classical", "provider_compatible", "unverified")
DOMAINS = (
    "self", "health", "character", "intellect", "education", "wealth", "family",
    "speech", "siblings", "courage", "mother", "home", "property", "vehicles",
    "children", "enemies", "disease", "servants", "marriage", "spouse",
    "relationships", "longevity", "fortune", "father", "religion", "career",
    "status", "fame", "gains", "losses", "expenses", "foreign", "travel",
    "spirituality", "relatives",
)
ID_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9_]+)+$")
REQUIRED = ("id", "when", "meaning", "polarity", "domains", "source", "provenance")
OPTIONAL = ("cross_check", "clauses", "variants", "flagged", "note")
CITATION_KEYS = ("book", "edition", "ch", "v")


class RuleError(ValueError):
    """A rule file that does not match the schema."""


def _check_citation(cite, where: str) -> None:
    if not isinstance(cite, dict) or set(cite) != set(CITATION_KEYS):
        raise RuleError(f"{where}: citation needs exactly {CITATION_KEYS}")
    if not all(str(cite[k]).strip() for k in CITATION_KEYS):
        raise RuleError(f"{where}: citation fields must be non-empty")
    if not isinstance(cite["ch"], int):
        raise RuleError(f"{where}: ch must be an integer")


def validate_rule(rule, where: str) -> None:
    """Raise RuleError unless ``rule`` follows the schema above."""
    if not isinstance(rule, dict):
        raise RuleError(f"{where}: a rule is a mapping")
    missing = [k for k in REQUIRED if k not in rule]
    if missing:
        raise RuleError(f"{where}: missing {missing}")
    extra = set(rule) - set(REQUIRED) - set(OPTIONAL)
    if extra:
        raise RuleError(f"{where}: unknown fields {sorted(extra)}")
    where = f"{where} ({rule['id']})"
    if not isinstance(rule["id"], str) or not ID_PATTERN.match(rule["id"]):
        raise RuleError(f"{where}: bad id")
    try:
        conditions.validate(rule["when"])
    except conditions.ConditionError as exc:
        raise RuleError(f"{where}: {exc}") from exc
    if not set(rule["when"]) & conditions.BINDING_KEYS:
        raise RuleError(f"{where}: when must bind a subject (lord_of or planet)")
    if not isinstance(rule["meaning"], str) or not rule["meaning"].strip():
        raise RuleError(f"{where}: meaning must be text")
    if rule["polarity"] not in POLARITIES:
        raise RuleError(f"{where}: polarity must be one of {POLARITIES}")
    domains = rule["domains"]
    if not isinstance(domains, list) or not domains or set(domains) - set(DOMAINS):
        raise RuleError(f"{where}: domains must be a non-empty list from DOMAINS")
    _check_citation(rule["source"], f"{where}.source")
    if "cross_check" in rule:
        _check_citation(rule["cross_check"], f"{where}.cross_check")
    if rule["provenance"] not in PROVENANCES:
        raise RuleError(f"{where}: provenance must be one of {PROVENANCES}")
    for i, clause in enumerate(rule.get("clauses", [])):
        cw = f"{where}.clauses[{i}]"
        if not isinstance(clause, dict) or set(clause) != {"when", "meaning", "polarity"}:
            raise RuleError(f"{cw}: needs exactly when, meaning, polarity")
        if clause["polarity"] not in POLARITIES:
            raise RuleError(f"{cw}: bad polarity")
        try:
            conditions.validate(clause["when"], bound=True, where=cw)
        except conditions.ConditionError as exc:
            raise RuleError(str(exc)) from exc
    variants = rule.get("variants", [])
    for i, var in enumerate(variants):
        if not isinstance(var, dict) or set(var) != {"edition", "reading"}:
            raise RuleError(f"{where}.variants[{i}]: needs exactly edition, reading")
    if bool(variants) != bool(rule.get("flagged", False)):
        raise RuleError(f"{where}: flagged must be true exactly when variants are recorded")


def load(directory: Path = RULES_DIR) -> list[dict]:
    """Load and validate every rule file; ids must be unique across files."""
    rules: list[dict] = []
    seen: dict[str, str] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise RuleError(f"{path.name}: a rule file is a list of rules")
        for i, rule in enumerate(data):
            validate_rule(rule, f"{path.name}[{i}]")
            if rule["id"] in seen:
                raise RuleError(f"{path.name}: duplicate id {rule['id']} (also in {seen[rule['id']]})")
            seen[rule["id"]] = path.name
            rules.append(rule)
    return rules


RULES: list[dict] = load()


def fired(chart: dict, rules: list[dict] | None = None) -> list[dict]:
    """Every rule whose condition holds in ``chart``, with its evidence.

    ``chart`` is the engine's chart JSON (``chart.build``); add the yoga
    report under ``chart["yogas"]`` for ``yoga_present`` conditions.
    """
    out = []
    for rule in RULES if rules is None else rules:
        ok, evidence = conditions.evaluate(rule["when"], chart)
        if not ok:
            continue
        subject = _subject(rule["when"], chart)
        hit = {k: rule[k] for k in ("id", "meaning", "polarity", "domains", "source",
                                    "provenance") }
        hit["subject"] = subject
        hit["evidence"] = evidence
        for key in ("cross_check", "variants", "flagged", "note"):
            if key in rule:
                hit[key] = rule[key]
        clauses = []
        for clause in rule.get("clauses", []):
            c_ok, c_ev = conditions.evaluate(clause["when"], chart, subject)
            if c_ok:
                clauses.append({"meaning": clause["meaning"], "polarity": clause["polarity"],
                                "evidence": c_ev})
        if clauses:
            hit["clauses"] = clauses
        out.append(hit)
    return out


def _subject(when: dict, chart: dict) -> str:
    if "lord_of" in when:
        return chart["houses"][when["lord_of"] - 1]["lord"]
    return when["planet"]
