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
    BPHS, "BPHS Chapter 3, shlokas 10-11: natural and contextual benefic/malefic."
)
GRAHA_DRISHTI = block(
    BPHS,
    "BPHS Chapter 26: special aspects for Mars, Jupiter and Saturn only. "
    "Rahu and Ketu take the ordinary seventh aspect here.",
)
RASHI_DRISHTI = block(BPHS, "BPHS/Jaimini rashi drishti; movable, fixed and dual.")

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
    "are BPHS Chapter 3, verses 66-70. The part index itself -- "
    "(lord index - vara) mod 8 -- is not in that passage: it was recovered by "
    "inverting Prokerala's longitudes back into the moment the Lagna held "
    "them. Marked provider_compatible because the indexing decides the answer, "
    "and these are only correct under prokerala_compatible.",
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
