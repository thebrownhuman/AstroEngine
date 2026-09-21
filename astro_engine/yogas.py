"""Yoga detection.

The 21 yogas Prokerala's /astrology/yoga endpoint returns, using their exact
names and group order, plus three extras of our own.

Note their published OpenAPI example is out of date: it shows 24 yogas with
different spellings ("Kedar", "Sunafa", "Veshi"). The live API returns 21, spelt
"Kedara", "Sunapha", "Vesi", and omits Chandal, Kuja and Kemdrum entirely. The
live names are authoritative here.

Each detector returns the evidence behind its verdict, so a wrong answer can be
diagnosed rather than merely observed. `VERIFIED` records which ones were
checked against the live API, and every yoga carries that flag in its output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import provenance
from .constants import SIGNS_EN, SIGN_LORDS

KENDRAS = (1, 4, 7, 10)
TRIKONAS = (1, 5, 9)
DUSTHANAS = (6, 8, 12)
FIXED_SIGNS = (1, 4, 7, 10)  # Taurus, Leo, Scorpio, Aquarius

SEVEN_GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NODES = ("Rahu", "Ketu")

# Panchamahapurusha: graha -> yoga name. Requires own sign or exaltation in a kendra.
MAHAPURUSHA = {
    "Mars": "Ruchaka Yoga",
    "Mercury": "Bhadra Yoga",
    "Jupiter": "Hamsa Yoga",
    "Venus": "Malavya Yoga",
    "Saturn": "Sasa Yoga",
}

# BPHS Chapter 26 special aspects, as house counts from the occupied house.
# Rahu and Ketu are not assigned additional 5th/9th aspects in that passage.
SPECIAL_ASPECTS = {"Mars": (4, 7, 8), "Jupiter": (5, 7, 9), "Saturn": (3, 7, 10)}


@dataclass
class Yoga:
    name: str
    group: str
    present: bool
    reason: str
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "group": self.group,
            "has_yoga": self.present,
            "reason": self.reason,
            "parity": (
                "verified" if self.name in VERIFIED
                else "verified_negative_only" if self.name in WEAKLY_VERIFIED
                else "not_in_prokerala_set" if self.name in EXTRA
                else "unverified"
            ),
            "evidence": self.evidence,
            **(provenance.DARIDRA if self.name in UNVERIFIED
               else provenance.YOGA),
        }


class ChartView:
    """Convenience accessors over a chart produced by `chart.build()`."""

    def __init__(self, chart: dict):
        self.chart = chart
        self.grahas = chart["grahas"]
        self.lagna_sign = chart["lagna"]["sign_index"]

    def house(self, graha: str) -> int:
        return self.grahas[graha]["house"]

    def sign(self, graha: str) -> int:
        return self.grahas[graha]["sign_index"]

    def house_from(self, graha: str, reference: str) -> int:
        return (self.sign(graha) - self.sign(reference)) % 12 + 1

    def lord_of_house(self, house: int) -> str:
        return SIGN_LORDS[(self.lagna_sign + house - 1) % 12]

    def houses_ruled_by(self, graha: str) -> list[int]:
        return [h for h in range(1, 13) if self.lord_of_house(h) == graha]

    def occupants(self, house: int) -> list[str]:
        return [g for g in self.grahas if self.house(g) == house]

    def in_same_sign(self, a: str, b: str) -> bool:
        return self.sign(a) == self.sign(b)

    def aspects(self, source: str, target_house: int) -> bool:
        """BPHS graha drishti from `source` onto a house."""
        counts = SPECIAL_ASPECTS.get(source, (7,))
        origin = self.house(source)
        return target_house in {(origin - 1 + (c - 1)) % 12 + 1 for c in counts}

    def dignified(self, graha: str) -> bool:
        return self.grahas[graha]["dignity"]["state"] in ("own_sign", "exalted")


# --- major yogas -------------------------------------------------------------

def gajakesari(view: ChartView) -> Yoga:
    """Jupiter in a kendra from the Moon."""
    position = view.house_from("Jupiter", "Moon")
    present = position in KENDRAS
    return Yoga(
        "Gajakesari Yoga", "Major Yogas", present,
        f"Jupiter is in the {position} from the Moon"
        + ("" if present else f"; a kendra {KENDRAS} is required"),
        {"jupiter_house_from_moon": position},
    )


def mahapurusha(view: ChartView, graha: str) -> Yoga:
    """Panchamahapurusha: the graha in its own or exaltation sign, in a kendra.

    Measured from the Lagna. Some traditions also allow a kendra from the Moon;
    `kendra_from_moon` is reported so the looser reading stays available.
    """
    state = view.grahas[graha]["dignity"]["state"]
    house = view.house(graha)
    dignified = state in ("own_sign", "exalted")
    present = dignified and house in KENDRAS
    if not dignified:
        reason = f"{graha} is {state}, not in its own sign or exaltation"
    elif not present:
        reason = f"{graha} is {state} but in house {house}, not a kendra"
    else:
        reason = f"{graha} is {state} in house {house}, a kendra"
    return Yoga(
        MAHAPURUSHA[graha], "Major Yogas", present, reason,
        {
            "graha": graha,
            "dignity": state,
            "house_from_lagna": house,
            "kendra_from_moon": view.house_from(graha, "Moon") in KENDRAS,
        },
    )


def _occupied_signs(view: ChartView) -> set[int]:
    return {view.sign(g) for g in SEVEN_GRAHAS}


def kedara(view: ChartView) -> Yoga:
    """Nabhasa Sankhya yoga: the seven grahas spread across exactly four signs."""
    signs = _occupied_signs(view)
    present = len(signs) == 4
    return Yoga(
        "Kedara Yoga", "Major Yogas", present,
        f"the seven grahas occupy {len(signs)} signs; Kedara needs exactly 4",
        {"occupied_sign_count": len(signs),
         "signs": sorted(SIGNS_EN[s] for s in signs)},
    )


def kamala(view: ChartView) -> Yoga:
    """All seven grahas spread across all four kendras from the Lagna.

    Not merely "within the kendras": every one of the four must be occupied.
    Verified - a chart with all seven crowded into three kendras is not Kamala.
    """
    houses = {view.house(g) for g in SEVEN_GRAHAS}
    present = houses == set(KENDRAS)
    return Yoga(
        "Kamal Yoga", "Major Yogas", present,
        f"the seven grahas occupy houses {sorted(houses)}; "
        f"Kamala needs every one of {list(KENDRAS)} occupied",
        {"occupied_houses": sorted(houses), "kendras_occupied": sorted(houses & set(KENDRAS))},
    )


def musala(view: ChartView) -> Yoga:
    """All seven grahas in fixed signs."""
    signs = _occupied_signs(view)
    present = all(s in FIXED_SIGNS for s in signs)
    return Yoga(
        "Musala Yoga", "Major Yogas", present,
        "all seven grahas are in fixed signs" if present
        else "not all grahas are in fixed signs",
        {"signs": sorted(SIGNS_EN[s] for s in signs),
         "fixed_signs": [SIGNS_EN[s] for s in FIXED_SIGNS]},
    )


def kahala(view: ChartView) -> Yoga:
    """The 4th and 9th lords in mutual kendras, with an exalted Lagna lord.

    WEAKLY VERIFIED. Prokerala reported Kahala as absent on all 21 test charts,
    so the rule was never exercised in the positive direction. Requiring the
    Lagna lord merely to be dignified (own sign or exaltation) produced three
    false positives against them; requiring exaltation removes those. That is
    consistent with their output but not proof of it - no chart in the sample
    shows what makes them say yes.
    """
    fourth, ninth = view.lord_of_house(4), view.lord_of_house(9)
    separation = (view.sign(ninth) - view.sign(fourth)) % 12 + 1
    mutual_kendra = separation in KENDRAS
    lagna_lord = view.lord_of_house(1)
    strong = view.grahas[lagna_lord]["dignity"]["state"] == "exalted"
    present = mutual_kendra and strong
    return Yoga(
        "Kahala Yoga", "Major Yogas", present,
        f"4th lord {fourth} and 9th lord {ninth} are {separation} apart "
        f"({'kendra' if mutual_kendra else 'not a kendra'}); "
        f"lagna lord {lagna_lord} is {'exalted' if strong else 'not exalted'}",
        {"fourth_lord": fourth, "ninth_lord": ninth, "separation": separation,
         "lagna_lord": lagna_lord, "lagna_lord_dignified": strong},
    )


def raja_yoga(view: ChartView) -> Yoga:
    """A kendra lord and a trikona lord joined by conjunction or mutual aspect.

    Two findings from verification, both against the common textbook reading:
    a one-way aspect does not count, and a single graha owning both a kendra and
    a trikona (a yogakaraka) does not by itself make the yoga. Both variants
    were tested and rejected; this rule matches on all 21 charts.
    """
    kendra_lords = {view.lord_of_house(h) for h in KENDRAS}
    trikona_lords = {view.lord_of_house(h) for h in TRIKONAS}

    links = []
    for a in sorted(kendra_lords):
        for b in sorted(trikona_lords):
            if a == b:
                continue
            if view.in_same_sign(a, b):
                links.append({"between": [a, b], "type": "conjunction"})
            elif view.aspects(a, view.house(b)) and view.aspects(b, view.house(a)):
                links.append({"between": [a, b], "type": "mutual_aspect"})

    present = bool(links)
    return Yoga(
        "Raja Yoga", "Major Yogas", present,
        f"{len(links)} kendra-trikona link(s) by conjunction or mutual aspect",
        {
            "links": links,
            "kendra_lords": sorted(kendra_lords),
            "trikona_lords": sorted(trikona_lords),
            "yogakarakas": sorted(kendra_lords & trikona_lords - {view.lord_of_house(1)}),
            "note": "a yogakaraka alone does not create the yoga in this ruleset",
        },
    )


# --- chandra yogas -----------------------------------------------------------

def _companions(view: ChartView, reference: str, exclude: tuple[str, ...]) -> dict:
    second = [g for g in view.occupants((view.house(reference) % 12) + 1)
              if g not in exclude and g != reference]
    twelfth = [g for g in view.occupants(((view.house(reference) - 2) % 12) + 1)
               if g not in exclude and g != reference]
    return {"second": second, "twelfth": twelfth}


def sunapha(view: ChartView) -> Yoga:
    # BPHS Ch. 37, vv. 7-10 says "a planet, other than the Sun"; nodes are
    # planets in the book's nine-graha list and are not excluded here.
    c = _companions(view, "Moon", ("Sun",))
    present = bool(c["second"])
    return Yoga("Sunapha Yoga", "Chandra Yogas", present,
                f"2nd from Moon holds {c['second'] or 'nothing'}", c)


def anapha(view: ChartView) -> Yoga:
    c = _companions(view, "Moon", ("Sun",))
    present = bool(c["twelfth"])
    return Yoga("Anapha Yoga", "Chandra Yogas", present,
                f"12th from Moon holds {c['twelfth'] or 'nothing'}", c)


def duradhara(view: ChartView) -> Yoga:
    c = _companions(view, "Moon", ("Sun",))
    present = bool(c["second"]) and bool(c["twelfth"])
    return Yoga("Duradhara Yoga", "Chandra Yogas", present,
                f"2nd holds {c['second'] or 'nothing'}, "
                f"12th holds {c['twelfth'] or 'nothing'}", c)


def kemadruma(view: ChartView, name: str = "Kemadruma Yoga",
              group: str = "Chandra Yogas") -> Yoga:
    """BPHS Chapter 37, verses 11-13.

    Excluding the Sun, no planet may be with the Moon, in the 2nd or 12th
    from the Moon, or in an angle from the Ascendant.
    """
    planets = tuple(view.grahas)
    with_moon = [
        graha for graha in planets
        if graha not in ("Sun", "Moon")
        and view.sign(graha) == view.sign("Moon")
    ]
    second = [
        graha for graha in planets
        if graha != "Sun" and view.house_from(graha, "Moon") == 2
    ]
    twelfth = [
        graha for graha in planets
        if graha != "Sun" and view.house_from(graha, "Moon") == 12
    ]
    kendra = {
        str(house): [
            graha for graha in planets
            if graha != "Sun" and view.house(graha) == house
        ]
        for house in KENDRAS
    }
    kendra = {house: occupants for house, occupants in kendra.items() if occupants}
    present = not (with_moon or second or twelfth or kendra)
    return Yoga(
        name,
        group,
        present,
        "no planet other than the Sun is in any BPHS-prohibited position"
        if present else "a BPHS Kemadruma cancellation condition is present",
        {
            "with_moon": with_moon,
            "second_from_moon": second,
            "twelfth_from_moon": twelfth,
            "kendra_from_lagna": kendra,
            "rule_source": "BPHS Chapter 37, verses 11-13",
        },
    )


# --- soorya yogas ------------------------------------------------------------

def vesi(view: ChartView) -> Yoga:
    # BPHS Ch. 38, v. 1 excludes the Moon; the remaining grahas are eligible.
    c = _companions(view, "Sun", ("Moon",))
    present = bool(c["second"])
    return Yoga("Vesi Yoga", "Soorya Yogas", present,
                f"2nd from Sun holds {c['second'] or 'nothing'}", c)


def vasi(view: ChartView) -> Yoga:
    c = _companions(view, "Sun", ("Moon",))
    present = bool(c["twelfth"])
    return Yoga("Vasi Yoga", "Soorya Yogas", present,
                f"12th from Sun holds {c['twelfth'] or 'nothing'}", c)


def ubhayachari(view: ChartView) -> Yoga:
    c = _companions(view, "Sun", ("Moon",))
    present = bool(c["second"]) and bool(c["twelfth"])
    return Yoga("Ubhaya Chari Yoga", "Soorya Yogas", present,
                f"2nd holds {c['second'] or 'nothing'}, "
                f"12th holds {c['twelfth'] or 'nothing'}", c)


# --- inauspicious yogas ------------------------------------------------------

def daridra(view: ChartView) -> Yoga:
    """The 11th lord fallen into a dusthana.

    NOT VERIFIED against Prokerala. Their rule could not be recovered: it
    disagrees with the classical definition on 3 of 21 charts, and no
    combination of up to three house-lord placement predicates reproduces their
    output. It is lagna-dependent -- the same date and place flips the verdict
    when the birth time changes -- so it is house-based. Beyond that it has
    resisted everything.

    The search is worth recording, because the negative result is solid rather
    than an admission of running out of ideas. Fifteen charts left twenty-seven
    one- and two-term formulas fitting perfectly, which is what too little
    signal looks like, not success. So twenty-four further charts were chosen
    specifically where those twenty-seven disagreed most sharply -- each one
    splitting the field about in half -- and fetched. All twenty-seven died.

    On the resulting thirty-nine charts, an exhaustive bitmask search over 378
    predicates (house lordships, placements, dusthana and kendra membership,
    retrogression, combustion, conjunctions with benefics and malefics) finds
    **no formula in one, two or three terms**. That is a strong statement: with
    39 independent verdicts, a candidate fits by luck with probability 2**-39,
    so across the whole search the expected number of spurious fits is about
    1e-5. If a three-term rule existed, it would have shown.

    So Prokerala's Daridra is either a longer formula, or uses something this
    engine does not model -- shadbala, a divisional chart, or an aspect scheme.
    The classical definition is kept here and the result is flagged. Treat it
    as our own opinion, not as parity.

    Reproduce with validation/pin_daridra.py and validation/search_daridra.py.
    """
    lord = view.lord_of_house(11)
    house = view.house(lord)
    present = house in DUSTHANAS
    return Yoga("Daridra Yoga", "Inauspicious Yogas", present,
                f"11th lord {lord} sits in house {house}",
                {"eleventh_lord": lord, "house": house})


def grahan(view: ChartView) -> Yoga:
    """Sun or Moon in the same sign as Rahu or Ketu."""
    pairs = [
        (light, node) for light in ("Sun", "Moon") for node in NODES
        if view.in_same_sign(light, node)
    ]
    return Yoga("Grahan Yoga", "Inauspicious Yogas", bool(pairs),
                ", ".join(f"{a} with {b}" for a, b in pairs) or
                "neither luminary is with a node",
                {"conjunctions": [list(p) for p in pairs]})


def shakat(view: ChartView) -> Yoga:
    """The Moon in the 6th, 8th or 12th from Jupiter."""
    position = view.house_from("Moon", "Jupiter")
    present = position in DUSTHANAS
    return Yoga("Shakat Yoga", "Inauspicious Yogas", present,
                f"the Moon is in the {position} from Jupiter",
                {"moon_house_from_jupiter": position})


def chandal(view: ChartView) -> Yoga:
    """Guru Chandal: Jupiter in the same sign as Rahu, or as Ketu."""
    with_rahu = view.in_same_sign("Jupiter", "Rahu")
    with_ketu = view.in_same_sign("Jupiter", "Ketu")
    present = with_rahu or with_ketu
    return Yoga("Chandal Yoga", "Inauspicious Yogas", present,
                "Jupiter is with " + ("Rahu" if with_rahu else "Ketu") if present
                else "Jupiter is not with a node",
                {"with_rahu": with_rahu, "with_ketu": with_ketu})


def kuja(view: ChartView) -> Yoga:
    """Mangal dosha: Mars in the 1st, 2nd, 4th, 7th, 8th or 12th from the Lagna."""
    house = view.house("Mars")
    houses = (1, 2, 4, 7, 8, 12)
    present = house in houses
    return Yoga("Kuja Yoga", "Inauspicious Yogas", present,
                f"Mars occupies house {house}",
                {"mars_house": house, "dosha_houses": list(houses)})


def kemdrum(view: ChartView) -> Yoga:
    """Their list carries Kemadruma twice under two spellings."""
    return kemadruma(view, name="Kemdrum Yoga", group="Inauspicious Yogas")


# --- assembly ----------------------------------------------------------------

GROUP_ORDER = ("Major Yogas", "Chandra Yogas", "Soorya Yogas", "Inauspicious Yogas")

# Identical to Prokerala on all 21 test charts, with both verdicts observed for
# each - so the rule is exercised in both directions, not just agreeing on
# absence.
VERIFIED = frozenset({
    "Gajakesari Yoga", "Kedara Yoga", "Musala Yoga", "Raja Yoga",
    "Ruchaka Yoga", "Bhadra Yoga", "Hamsa Yoga", "Malavya Yoga", "Sasa Yoga",
    "Sunapha Yoga", "Anapha Yoga", "Duradhara Yoga", "Kemadruma Yoga",
    "Vesi Yoga", "Vasi Yoga", "Ubhaya Chari Yoga", "Grahan Yoga", "Shakat Yoga",
})

# Agrees on all 21 charts, but Prokerala reported these as absent every time, so
# only the negative case is evidenced. Agreement here is weak: a detector that
# never fires would score identically.
WEAKLY_VERIFIED = frozenset({"Kahala Yoga", "Kamal Yoga"})

# Their rule could not be recovered; see the detector docstring.
UNVERIFIED = frozenset({"Daridra Yoga"})

# Ours, not part of Prokerala's set. Kuja Yoga is the familiar Mangal dosha.
EXTRA = frozenset({"Chandal Yoga", "Kuja Yoga", "Kemdrum Yoga"})


def detect(chart: dict) -> list[Yoga]:
    """All 24, in Prokerala's order."""
    view = ChartView(chart)
    return [
        gajakesari(view), kedara(view), kahala(view), kamala(view), musala(view),
        raja_yoga(view),
        mahapurusha(view, "Mars"), mahapurusha(view, "Mercury"),
        mahapurusha(view, "Jupiter"), mahapurusha(view, "Venus"),
        mahapurusha(view, "Saturn"),
        sunapha(view), anapha(view), duradhara(view), kemadruma(view),
        vesi(view), vasi(view), ubhayachari(view),
        daridra(view), grahan(view), shakat(view), chandal(view),
        kuja(view), kemdrum(view),
    ]


def report(chart: dict) -> dict:
    found = detect(chart)
    groups = []
    for group in GROUP_ORDER:
        members = [y for y in found if y.group == group]
        count = sum(y.present for y in members)
        groups.append({
            "name": group,
            "count": count,
            "yoga_list": [y.as_dict() for y in members],
        })
    return {
        "yoga_details": groups,
        "present": sorted(y.name for y in found if y.present),
        "total_present": sum(y.present for y in found),
    }
