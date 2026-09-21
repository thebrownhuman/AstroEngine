"""Where each rule in this engine comes from.

`parity` already answers a different question -- does this reproduce
Prokerala's number -- and the two are orthogonal. A table can match Prokerala
on every cell and still have no textual authority behind it, which is exactly
the case for most of the porutham grid. An LLM reading this JSON cannot tell
the two apart from the numbers, so it has to be told.

Attach `source` next to `parity`, never instead of it.
"""

from __future__ import annotations

# The vocabulary. Four values, and nothing else may be emitted.
BPHS = "bphs"
CLASSICAL = "classical"
PROVIDER = "provider_compatible"
UNVERIFIED = "unverified"

SOURCES = frozenset({BPHS, CLASSICAL, PROVIDER, UNVERIFIED})

SOURCE_MEANINGS = {
    BPHS: (
        "Traceable to Brihat Parashara Hora Shastra; the citation is in the "
        "`authority` field."
    ),
    CLASSICAL: (
        "Standard Jyotisha or an established named system, but not defined in "
        "BPHS. Treat as conventional practice, not scripture."
    ),
    PROVIDER: (
        "Reproduces Prokerala's output and was recovered by measuring it. No "
        "textual authority: do not present these as classical doctrine."
    ),
    UNVERIFIED: (
        "Neither reproduced nor textually grounded. Do not rely on it."
    ),
}


def block(source: str, authority: str) -> dict:
    """The provenance stamp attached to one output block."""
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}; expected one of {sorted(SOURCES)}")
    return {"source": source, "authority": authority}


# --- per-block stamps ---------------------------------------------------------

GRAHA_NATURE = block(
    BPHS,
    "BPHS Chapter 3, shloka 11: the Sun, Saturn, Mars, a waning Moon and a "
    "Mercury joined to a malefic are malefic, the rest benefic; a waning Moon "
    "conjunct or aspected by a benefic turns benefic, and a waning Moon "
    "together with Mercury makes both benefic."
)
GRAHA_DRISHTI = block(
    BPHS,
    "BPHS Chapter 26, verses 2-5: \"All planets aspect the 7th fully. Saturn, "
    "Jupiter and Mars have special aspects respectively on 3rd and 10th, 5th "
    "and 9th, and 4th and 8th.\" The passage names three grahas and no more, "
    "so Rahu and Ketu take only the ordinary seventh aspect.",
)
RASHI_DRISHTI = block(
    BPHS,
    "BPHS Chapter 8, 'Aspects of the Signs': rashi drishti among movable, "
    "fixed and dual signs, kept separate from graha drishti.",
)

NAKSHATRA_DEITY = block(BPHS, "BPHS Chapter 3 nakshatra deity list.")
NAKSHATRA_METADATA = block(
    PROVIDER,
    "Ganam, symbol, animal sign, nadi, colour, direction, syllables, birth "
    "stone, gender, planet and enemy yoni are transcribed from Prokerala's "
    "birth-details, not from BPHS. The `deity` field is the exception and is "
    "BPHS; see nakshatra_deity_source.",
)

UPAGRAHA_SOLAR = block(
    CLASSICAL,
    "The five sun-derived upagrahas are fixed offsets from the Sun, standard "
    "across the classical sources.",
)
UPAGRAHA_TIME = block(
    PROVIDER,
    "Mixed authority. The eight-part division of day and night, Gulika at the "
    "start of Saturn's portion, and Mandi being the same upagraha as Gulika "
    "(\"Gulika and Mandi are one and the same and not different\") are BPHS "
    "Chapter 3, verses 66-69. The part index itself -- "
    "(lord index - vara) mod 8 -- is not in that passage: it was recovered by "
    "inverting Prokerala's longitudes back into the moment the Lagna held "
    "them. Marked provider_compatible because the indexing decides the answer, "
    "and these are only correct under prokerala_compatible.",
)

DASHA = block(
    BPHS,
    "Vimshottari itself is BPHS Chapter 46: the 120-year cycle, the nakshatra "
    "lords and their year counts. Two conventions that move the boundaries are "
    "not from the text and are settings, not doctrine. The year length is a "
    "live disagreement between implementations - 365.25 Julian (the default "
    "here, and what Prokerala uses), 365.2425 Gregorian, or 365.2564 sidereal "
    "- and over 120 years the first two diverge by about 0.9 days. Separately, "
    "`prokerala_compatible` rounds the nakshatra traversal fraction to three "
    "decimals, which costs up to ~1.5 days on a 20-year mahadasha.",
)

PANCHANGA = block(
    CLASSICAL,
    "The five limbs are standard panchang, not a BPHS construct. Tithi, yoga "
    "and karana depend only on the Sun-Moon elongation, so they are geometry "
    "rather than rule; the vara depends on the sunrise convention and so "
    "shifts with prokerala_compatible.",
)

DIGNITY = block(
    BPHS,
    "Exaltation, debilitation and own sign follow the BPHS tables; "
    "debilitation is taken as the seventh sign from exaltation. The "
    "combustion orbs are the conventional per-graha values rather than a "
    "BPHS list.",
)

HOUSE_SIGNIFICATIONS = block(
    CLASSICAL,
    "The one-line significations are an editorial summary for reading "
    "convenience, not a quotation from any chapter. The house lords and "
    "occupants beside them are computed, not editorial.",
)

RELATIONSHIP = block(
    BPHS,
    "Naisargika friendship is the BPHS table, written out rather than derived "
    "because the derivation has exceptions and does not cover the nodes. "
    "Tatkalika and the five-fold panchadha compound are the standard rules. "
    "Two asymmetries in how the nodes participate are Prokerala's and are "
    "reproduced deliberately.",
)

CALENDAR = block(
    CLASSICAL,
    "Ayana turns on the Sun's sidereal sign, not the tropical solstice, though "
    "the labels follow Prokerala in naming each half after the solstice that "
    "opens it. Only the drik ritu is emitted: Prokerala's vedic ritu "
    "boundaries came back exactly 59 days apart, which matches neither two "
    "lunar months nor two solar months, and one sample was not enough to "
    "recover it. Sudarshana Chakra is the ordinary three-reference reading.",
)

VARGA = block(
    BPHS,
    "The shodasavarga: BPHS Chapter 6 defines the sixteen divisions and "
    "Chapter 7 their deities and uses. Every mapping here is the classical "
    "one; `parity` says separately which have been checked placement-for-"
    "placement against Prokerala.",
)

ASHTAKAVARGA = block(
    BPHS,
    "The bindu contribution tables are BPHS Chapter 66, and the trinal "
    "reduction is Chapter 67. The row totals (48, 49, 39, 54, 56, 52, 39) and "
    "their sum of 337 are asserted at import so a mistyped digit fails "
    "immediately.",
)
EKADHIPATYA = block(
    PROVIDER,
    "This one contradicts BPHS and does so deliberately. Chapter 68 is not "
    "silent on the tie case: its worked example gives Capricorn and Aquarius "
    "the same trikona-corrected number 2, and because Capricorn holds planets "
    "and Aquarius does not, it reduces Aquarius to zero. This engine leaves "
    "the empty sign alone on an exact tie, which is what Prokerala does and "
    "what 204/204 measured checks require. Chapter 68 is also internally "
    "inconsistent - its Taurus/Libra example does not follow its own rule (1) "
    "for two planetless signs - so following the text would not settle the "
    "matter either. Treat these numbers as Prokerala's, not as Parashara's.",
)

TRANSIT = block(
    CLASSICAL,
    "Gochara is not BPHS. Sade Sati, Dhaiyya, Kantaka and Ashtama Shani are "
    "standard practice, and the ingress dates here are computed by bisecting "
    "the ephemeris rather than taken from any table. The phase labels and the "
    "`description` wording reproduce Prokerala's own strings so the two can be "
    "compared directly; treat that prose as theirs, not as doctrine.",
)

KAAL_SARPA = block(
    PROVIDER,
    "The modern all-grahas-between-the-nodes rule. BPHS describes Sarpa Yoga "
    "-- malefics in kendras -- which is a different construct; this is not it. "
    "Two charts of eighteen disagree with Prokerala and are left disagreeing.",
)
PAPASAMYAM = block(
    PROVIDER,
    "Weights measured from Prokerala: one point from the Lagna, half from the "
    "Moon, a quarter from Venus, regardless of which malefic carries it.",
)

MATCHING = block(
    PROVIDER,
    "Ashtakoot guna milan. Several koot tables differ from the published ones "
    "-- three vasya cells, two gana cells, the yoni friend/enemy pairs, and "
    "Stree Deergha starting at count nine -- and are carried as measured.",
)
PORUTHAM = block(
    PROVIDER,
    "All twelve Tamil checks reproduce Prokerala, but Rasi and Vashya are "
    "carried as measured 12x12 tables because their classical forms fit only "
    "100 and 42 of 144 cells. Rajju and Nadi are likewise not the classical "
    "body bands. Corrected for Prokerala's pada off-by-one.",
)

MUHURTA = block(
    PROVIDER,
    "Choghadiya, hora, the kaal periods, Abhijit and Brahma Muhurat are "
    "panchang conventions, not BPHS. The night choghadiya list runs backwards "
    "through the cycle, two places per slot, as measured.",
)
GOWRI = block(
    PROVIDER,
    "The Gowri Nalla Neram table is not defined in BPHS. One Saturday-night "
    "slot differs: this engine gives Rogam where Prokerala gives Soram, "
    "because their rotation repeats a name instead of closing. Left "
    "disagreeing rather than matched to their inconsistency.",
)
BALA = block(
    CLASSICAL,
    "Tara bala, chandra bala and chandrashtama are standard panchang tables, "
    "not BPHS. Both daily tables reproduce Prokerala.",
)

KP = block(
    CLASSICAL,
    "Krishnamurti Paddhati: a named twentieth-century system with Placidus "
    "cusps and Vimshottari sub-division. Deliberately outside BPHS, which "
    "uses neither.",
)
NUMEROLOGY = block(
    CLASSICAL,
    "Pythagorean and Chaldean numerology. Not Jyotisha at all and not in "
    "BPHS; included because Prokerala exposes it.",
)

YOGA = block(
    CLASSICAL,
    "Standard yoga definitions. The five Panchamahapurusha, Gajakesari and the "
    "Sunapha/Anapha/Duradhara group are BPHS; the rest are common Jyotisha "
    "combinations stated the same way across the sources. `parity` says "
    "separately whether the detector reproduces Prokerala's verdict.",
)

DARIDRA = block(
    UNVERIFIED,
    "No BPHS rule found and no formula recovered. An exhaustive search over "
    "378 predicates in up to three terms across 39 charts found nothing; at "
    "39 independent verdicts a chance fit has probability 2**-39, so a short "
    "rule would have shown. Prokerala's must be longer or use something this "
    "engine does not model.",
)
