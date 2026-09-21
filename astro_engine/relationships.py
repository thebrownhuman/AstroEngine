"""Planetary friendship: natural, temporal and the five-fold compound.

Natural (naisargika) friendship is fixed and comes from BPHS Chapter 3, verse
55: a graha befriends the lords of its exaltation sign and of the 2nd, 4th,
5th, 8th, 9th and 12th from its **Moola-Trikona** -- not from its own sign, as
this comment said for a long time. The two coincide for most grahas, and the
table below is written out rather than derived, so the output was never wrong;
but anyone re-deriving it from the old wording would have got some of it wrong.
The table stays explicit because the derivation has exceptions and the nodes
are not in it at all.

Temporal (tatkalika) friendship depends on the chart: everything standing in
the 2nd, 3rd, 4th, 10th, 11th or 12th sign from a graha is its temporary
friend, everything in the 1st, 5th, 6th, 7th, 8th or 9th its temporary enemy.

The compound (panchadha maitri) folds the two into five grades:

    natural friend  + temporal friend -> Extreme Friend
    natural friend  + temporal enemy  -> Neutral
    natural neutral + temporal friend -> Friend
    natural neutral + temporal enemy  -> Enemy
    natural enemy   + temporal friend -> Neutral
    natural enemy   + temporal enemy  -> Extreme Enemy

Two asymmetries are Prokerala's and are reproduced deliberately. The nodes have
natural relationships *towards* the seven grahas but are never the object of
one, so "Sun -> Rahu" is No Relation while "Rahu -> Sun" is Enemy. And the
Ascendant appears in every table only to be given No Relation throughout;
it does take part in the temporal table, because it has a sign like anything
else, but a No Relation natural grade leaves the compound grade No Relation.
"""

from __future__ import annotations

SEVEN = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
NODES = ("Rahu", "Ketu")
ASCENDANT = "Ascendant"
# Prokerala's listing order for every relationship table.
BODIES = SEVEN + (ASCENDANT,) + NODES

FRIEND = "Friend"
NEUTRAL = "Neutral"
ENEMY = "Enemy"
NO_RELATION = "No Relation"
EXTREME_FRIEND = "Extreme Friend"
EXTREME_ENEMY = "Extreme Enemy"

NATURAL_FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
    "Rahu": {"Venus", "Jupiter", "Saturn"},
    "Ketu": {"Venus", "Mars", "Saturn"},
}
NATURAL_ENEMIES = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
    "Rahu": {"Sun", "Moon", "Mars"},
    "Ketu": {"Sun", "Moon"},
}

# Signs counted from a graha in which another graha is its temporary friend.
TEMPORAL_FRIEND_HOUSES = frozenset({2, 3, 4, 10, 11, 12})

COMPOUND = {
    (FRIEND, FRIEND): EXTREME_FRIEND,
    (FRIEND, ENEMY): NEUTRAL,
    (NEUTRAL, FRIEND): FRIEND,
    (NEUTRAL, ENEMY): ENEMY,
    (ENEMY, FRIEND): NEUTRAL,
    (ENEMY, ENEMY): EXTREME_ENEMY,
}

VEDIC_NAMES = {
    "Sun": "Ravi", "Moon": "Chandra", "Mercury": "Budha", "Venus": "Shukra",
    "Mars": "Kuja", "Jupiter": "Guru", "Saturn": "Shani",
    "Ascendant": "Lagna", "Rahu": "Rahu", "Ketu": "Ketu",
}
BODY_IDS = {
    "Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3, "Mars": 4,
    "Jupiter": 5, "Saturn": 6, "Ascendant": 100, "Rahu": 101, "Ketu": 102,
}


def natural(first: str, second: str) -> str:
    """Only the nine grahas have natural relationships, and only towards the
    seven -- the nodes and the Lagna are never the object of one."""
    if first == second or first == ASCENDANT or second not in SEVEN:
        return NO_RELATION
    if second in NATURAL_FRIENDS[first]:
        return FRIEND
    if second in NATURAL_ENEMIES[first]:
        return ENEMY
    return NEUTRAL


def temporal(first_sign: int, second_sign: int) -> str:
    distance = (second_sign - first_sign) % 12 + 1
    return FRIEND if distance in TEMPORAL_FRIEND_HOUSES else ENEMY


def compound(natural_grade: str, temporal_grade: str) -> str:
    return COMPOUND.get((natural_grade, temporal_grade), NO_RELATION)


def _body(name: str) -> dict:
    return {"id": BODY_IDS[name], "name": name, "vedic_name": VEDIC_NAMES[name]}


def compute(chart: dict) -> dict:
    """Every ordered pair of the ten bodies, in all three schemes."""
    signs = {name: chart["grahas"][name]["sign_index"]
             for name in SEVEN + NODES}
    signs[ASCENDANT] = chart["lagna"]["sign_index"]

    def row(first: str, second: str) -> tuple[str, str, str]:
        nat = natural(first, second)
        if first == second:
            return nat, NO_RELATION, NO_RELATION
        # The Lagna has a sign, so it takes part in the temporal table even
        # though it has no natural relationship and therefore no compound one.
        tmp = temporal(signs[first], signs[second])
        return nat, tmp, compound(nat, tmp)

    tables: dict[str, list[dict]] = {
        "natural_relationship": [],
        "temporal_relationship": [],
        "compound_relationship": [],
    }
    for first in BODIES:
        for second in BODIES:
            grades = row(first, second)
            for key, grade in zip(tables, grades):
                tables[key].append({
                    "first_planet": _body(first),
                    "second_planet": _body(second),
                    "relationship": grade,
                })
    return tables
