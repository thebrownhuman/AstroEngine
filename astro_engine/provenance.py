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

NAKSHATRA_DEITY = block(
    BPHS,
    "BPHS Chapter 7, verses 24-26 (Sharma V1, the Bhamsha passage): the "
    "presiding deities, Ashwini Kumara through Poosha, with Abhijit's Aja "
    "left out of the 28 so that each of the 27 sits on its own star. One "
    "label follows the providers instead: BPHS names Ashlesha's deity Ahi "
    "(the serpent), reported here as Rahu, as Prokerala (8 stars measured) "
    "and VedIntel (25) both do.",
)
NAKSHATRA_METADATA = block(
    PROVIDER,
    "Ganam, symbol, animal sign, nadi, colour, direction, syllables, birth "
    "stone, gender, planet and enemy yoni are transcribed from Prokerala's "
    "birth-details, not from BPHS. The `deity` field is the exception and is "
    "BPHS; see nakshatra_deity_source.",
)

UPAGRAHA_SOLAR = block(
    BPHS,
    "The five sun-derived upagrahas (Dhuma, Vyatipata, Parivesha, Indrachapa, "
    "Upaketu) are fixed offsets from the Sun given verbatim in BPHS Chapter 3, "
    "verses 61-64 (Sharma V1); the engine reproduces the translator's worked "
    "example exactly.",
)
UPAGRAHA_TIME = block(
    PROVIDER,
    "Mixed authority. The eight-part division of day and night and Mandi "
    "being the same upagraha as Gulika (\"Gulika and Mandi are one and the "
    "same and not different\") are BPHS Chapter 3, verses 66-69. Placing "
    "Gulika at the start of Saturn's portion is not: the verse is ambiguous, "
    "and the translator's Dhruvanka method gives the end. The start follows "
    "Prokerala. The part index itself -- "
    "(lord index - vara) mod 8 -- is not in that passage: it was recovered by "
    "inverting Prokerala's longitudes back into the moment the Lagna held "
    "them. Marked provider_compatible because the indexing decides the answer, "
    "and these are only correct under prokerala_compatible.",
)

GULIKA_STRICT = block(
    BPHS,
    "strict_bphs: Gulika and Mandi are the Lagna at the end of Saturn's "
    "portion. The portion is BPHS Chapter 3, verses 66-69, whose day and "
    "night tables (Sharma V1) the part index reproduces for all seven varas; "
    "the end is the translator's Dhruvanka method (portion number times one "
    "eighth of the span).",
)

DASHA = block(
    BPHS,
    "Vimshottari itself is BPHS Chapter 46, which names it the dasha \"most "
    "appropriate for the general populace\", sets the span at the 120-year "
    "natural life, and tabulates the nakshatra lords against their years. "
    "Two conventions that move the boundaries are not from the text and are "
    "settings, not doctrine. The year length is a "
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
    "BPHS Chapter 3, verses 49-50: the exaltation signs of the seven grahas "
    "with their deepest degrees, and \"in the seventh sign from the said "
    "exaltation sign each planet has its own debilitation\". The combustion "
    "orbs are conventional per-graha values, not from that passage.",
)

HOUSE_SIGNIFICATIONS = block(
    CLASSICAL,
    "BPHS Chapter 11, verses 2-13 does give each house's indications, so this "
    "is not merely editorial - but this list is not that list. It follows "
    "later convention on two points where Chapter 11 is explicit: father is "
    "placed in the 9th here and in the 10th there (the text carries a note "
    "insisting on the 10th), and debts in the 6th here and the 10th there. It "
    "also adds terms absent from that chapter - speech, purva punya, the "
    "occult, moksha. Classical rather than BPHS for those reasons. The house "
    "lords and occupants beside them are computed, not editorial.",
)

RELATIONSHIP = block(
    BPHS,
    "BPHS Chapter 3: verse 55 gives naisargika friendship (the 2nd, 4th, 5th, "
    "8th, 9th and 12th lords from a graha's Moola-Trikona, plus its "
    "exaltation lord; the rest enemies; both at once means neutral), verse 56 "
    "tatkalika, and verses 57-58 the five-fold panchadha compound with the "
    "same grades used here. The table is written out rather than derived "
    "because the derivation has exceptions and does not cover the nodes. Two "
    "asymmetries in how the nodes participate are Prokerala's and are "
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
    "The shodasavarga: BPHS Chapter 6, verses 2-4 name all sixteen divisions "
    "from Kshetra and Hora through Shashtyamsa, and Chapter 7 gives their "
    "deities and uses. Every mapping here is the classical "
    "one; `parity` says separately which have been checked placement-for-"
    "placement against Prokerala.",
)

ASHTAKAVARGA = block(
    PROVIDER,
    "Mixed authority. The bindu contribution tables are BPHS Chapter 66, and "
    "the trinal reduction is Chapter 67 except for one case: when a trine "
    "holds a zero, BPHS says to leave that trine alone (\"tat trikonam na "
    "shodhayet\", Sharma V2 Ch.69 v4, whose example keeps 0, 3, 6), while "
    "this engine zeroes all three, as Prokerala does. The row totals (48, 49, 39, 54, 56, 52, 39) and "
    "their sum of 337 are asserted at import so a mistyped digit fails "
    "immediately.",
)
ANANDADI = block(
    PROVIDER,
    "Weekday against the Moon's star on the 28-star scheme, Sunday counting "
    "from Ashwini and each later weekday four stars on. The rule is the "
    "classical one; the window convention (every nakshatra between the "
    "date's sunrise and the next, read with the date's weekday) and nine of "
    "the twenty-eight labels were measured against Prokerala. Entries with "
    "label_parity 'unverified' carry the classical name.",
)
AUSPICIOUS_YOGA = block(
    CLASSICAL,
    "Amrit Siddhi, Sarvartha Siddhi, Guru and Ravi Pushya, Dwipushkar and "
    "Tripushkar from the standard muhurta tables (weekday with nakshatra, and "
    "for the Pushkar yogas a bhadra tithi). The search window -- from the "
    "date's sunrise to the end of the last nakshatra starting before the next "
    "sunrise -- was measured against Prokerala's auspicious-yoga on seven "
    "dates, all agreeing; only two of those dates hold any yoga, so most "
    "table rows are classical rather than measured.",
)
CHANDRASHTAMA = block(
    PROVIDER,
    "The Moon in the eighth sign from the natal Moon is classical. The yearly "
    "listing, its split by nakshatra and the peak (janma nakshatra plus "
    "fifteen) follow Prokerala's chandrashtama-periods, measured on seven "
    "births.",
)
SARVA_REDUCTIONS = block(
    PROVIDER,
    "Prokerala's reduced sarvashtakavarga, recovered by measurement and exact "
    "over seven births. It is not the BPHS Chapter 67-68 order: trikona omits "
    "the zero-in-a-trine rule, and ekaadhipatya is taken from the raw prastara "
    "with Rahu, Ketu and the lagna counted as occupants.",
)
EKADHIPATYA = block(
    PROVIDER,
    "This one contradicts BPHS and does so deliberately. On an exact tie "
    "between the two signs of one lord, the Sanskrit (Sharma V2 Ch.70 v5) "
    "reduces the planetless sign; this engine leaves the empty sign alone, "
    "which is what Prokerala does and what 204/204 measured checks require. "
    "Sharma's worked example has Capricorn and Aquarius both empty at 2 and "
    "clears both, which the engine also does. Treat these numbers as Prokerala's, not as Parashara's.",
)

TRANSIT = block(
    CLASSICAL,
    "Gochara is not in BPHS at all: the text has no transit chapter and never "
    "mentions Sade Sati. It, Dhaiyya, Kantaka and Ashtama Shani are "
    "standard practice, and the ingress dates here are computed by bisecting "
    "the ephemeris rather than taken from any table. The phase labels and the "
    "`description` wording reproduce Prokerala's own strings so the two can be "
    "compared directly; treat that prose as theirs, not as doctrine.",
)

KAAL_SARPA = block(
    PROVIDER,
    "The modern all-grahas-between-the-nodes rule. BPHS does have a Sarpa "
    "Yoga, at Chapter 35 verse 8 - malefics occupying three kendras, also "
    "called Bhujanga, with its effects at verse 22 - but that is a different "
    "construct and this is not it. "
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
    "Mostly BPHS, verified chapter by chapter: the five Panchamahapurusha are "
    "Chapter 75 verses 1-2 (Mars, Mercury, Jupiter, Venus or Saturn in own "
    "sign or exaltation, in a kendra from the Lagna - exactly the rule used "
    "here), Gajakesari is Chapter 36 verses 3-4, Sunapha/Anapha/Duradhara are "
    "the lunar yogas of Chapter 37, and Vesi/Vasi/Ubhaya Chari the solar "
    "yogas of Chapter 38. The remainder are common Jyotisha combinations "
    "stated the same way across the sources, which is why this is classical "
    "rather than bphs as a whole. `parity` says separately whether each "
    "detector reproduces Prokerala's verdict.",
)

# --- strict_bphs ------------------------------------------------------------
#
# Stamped in place of the blocks above when a request sets strict_bphs, on
# exactly the outputs that mode changes. Citations are Sharma's edition.

DASHA_STRICT = block(
    BPHS,
    "strict_bphs: Vimshottari per BPHS (Sharma V2 Ch.48 v12-15), with the "
    "balance at birth taken as Bhayata over Bhabhoga - the time the Moon has "
    "spent in the birth nakshatra over the time it spends in all of it - as "
    "V2 Ch.48 v16 prescribes, instead of the fraction of arc. Antardashas are "
    "proportional per V2 Ch.53 v1. The year length is still a setting.",
)
DIGNITY_STRICT = block(
    BPHS,
    "strict_bphs: `state` is the degree-level reading of BPHS Chapter 3, "
    "verses 49-54 (Sharma V1): exaltation and debilitation signs with their "
    "deepest degrees, and the Moolatrikona spans, so Mercury past 20 Virgo is "
    "own_sign and the Moon past 3 Taurus is moolatrikona. The combustion orbs "
    "are still conventional.",
)
ASHTAKAVARGA_STRICT = block(
    BPHS,
    "strict_bphs: the rekha tables as the Sanskrit of Sharma V2 Ch.68 v46-63 "
    "gives them, which differs from the common tables in four cells: in the "
    "Moon's, the Moon gives the 9th and Mars does not, and Jupiter gives the "
    "2nd rather than the 12th (v49-51); in Venus's, Mars gives the 4th rather "
    "than the 5th (v59-60). Row totals are unchanged. Trikona shodhana is V2 "
    "Ch.69 v3-5, leaving a trine that holds a zero untouched (v4).",
)
EKADHIPATYA_STRICT = block(
    BPHS,
    "strict_bphs: ekadhipatya shodhana per Sharma V2 Ch.70 v1-5, applied to "
    "the trikona-reduced table, including the tie: when one sign is occupied "
    "and the other is not and both hold the same number, the planetless sign "
    "is cleared (v5, \"sagrahagrahayos tulye sarvam samshodhyam agrahe\").",
)
SARVA_STRICT = block(
    BPHS,
    "strict_bphs: the reduced sarvashtakavarga is the column sum of the seven "
    "grahas' own strict reductions (Sharma V2 Ch.69-70), in the textbook order, "
    "rather than Prokerala's recovered sarva method.",
)
GAJAKESARI_STRICT = block(
    BPHS,
    "strict_bphs: Sharma V1 Ch.38 v3-4. Jupiter in a kendra from the Lagna or "
    "from the Moon, joined with or aspected by a benefic, and not debilitated, "
    "combust or in an enemy's sign.",
)

DARIDRA = block(
    UNVERIFIED,
    "No BPHS rule found and no formula recovered. An exhaustive search over "
    "378 predicates in up to three terms across 39 charts found nothing; at "
    "39 independent verdicts a chance fit has probability 2**-39, so a short "
    "rule would have shown. Prokerala's must be longer or use something this "
    "engine does not model.",
)
