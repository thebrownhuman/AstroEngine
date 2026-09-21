"""Static Jyotisha reference data. No computation here."""

SIGNS = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena",
]

SIGNS_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Vimshottari dasha lords in sequence, with period length in years.
DASHA_SEQUENCE = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
    ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17),
]
DASHA_TOTAL_YEARS = 120

# Nakshatra index -> Vimshottari lord. The 9-lord cycle repeats three times.
NAKSHATRA_LORDS = [DASHA_SEQUENCE[i % 9][0] for i in range(27)]

TITHI_NAMES = [
    "Shukla Pratipada", "Shukla Dwitiya", "Shukla Tritiya", "Shukla Chaturthi",
    "Shukla Panchami", "Shukla Shashthi", "Shukla Saptami", "Shukla Ashtami",
    "Shukla Navami", "Shukla Dashami", "Shukla Ekadashi", "Shukla Dwadashi",
    "Shukla Trayodashi", "Shukla Chaturdashi", "Purnima",
    "Krishna Pratipada", "Krishna Dwitiya", "Krishna Tritiya", "Krishna Chaturthi",
    "Krishna Panchami", "Krishna Shashthi", "Krishna Saptami", "Krishna Ashtami",
    "Krishna Navami", "Krishna Dashami", "Krishna Ekadashi", "Krishna Dwadashi",
    "Krishna Trayodashi", "Krishna Chaturdashi", "Amavasya",
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
]

# Spellings follow the live Prokerala API, which writes "Garija" and gives
# Vishti its alternative name Bhadra alongside.
MOVABLE_KARANAS = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garija", "Vanija", "Vishti / Bhadra",
]
FIXED_KARANAS = ["Shakuni", "Chatushpada", "Naga", "Kimstughna"]

WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

# Exaltation sign index and exact degree of deep exaltation.
EXALTATION = {
    "Sun": (0, 10.0), "Moon": (1, 3.0), "Mars": (9, 28.0), "Mercury": (5, 15.0),
    "Jupiter": (3, 5.0), "Venus": (11, 27.0), "Saturn": (6, 20.0),
    "Rahu": (1, 20.0), "Ketu": (7, 20.0),
}

OWN_SIGNS = {
    "Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
    "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10],
}

# Maximum elongation from the Sun at which a planet is considered combust.
COMBUSTION_ORB = {
    "Moon": 12.0, "Mars": 17.0, "Mercury": 14.0,
    "Jupiter": 11.0, "Venus": 10.0, "Saturn": 15.0,
}

NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
NATURAL_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}

# Prokerala spells five of the twenty-seven differently. Responses that have to
# read back identically to theirs use this list; everything internal uses
# NAKSHATRAS, and the two are index-for-index the same nakshatra.
PROKERALA_NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krithika", "Rohini", "Mrigashirsha", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishaka", "Anuradha",
    "Jyeshta", "Moola", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]
assert len(PROKERALA_NAKSHATRA_NAMES) == len(NAKSHATRAS)


# Per-nakshatra reference data. The deity field below follows BPHS Chapter 3,
# shlokas 10-11 and the accompanying nakshatra deity list. The other fields
# are retained for API compatibility but are not BPHS authority.
NAKSHATRA_ATTRIBUTE_FIELDS = (
    "deity",
    "ganam",
    "symbol",
    "animal_sign",
    "nadi",
    "color",
    "best_direction",
    "syllables",
    "birth_stone",
    "gender",
    "planet",
    "enemy_yoni",
)

NAKSHATRA_ATTRIBUTES = {
    0: {"deity": "Ashwini Kumara", "ganam": "Deva", "symbol": "Horse’s Head", "animal_sign": "Horse", "nadi": "Vata", "color": "Blood Red", "best_direction": "South", "syllables": "Chu, Che, Cho, La", "birth_stone": "Chrysoberyl", "gender": "Male", "planet": "Ketu", "enemy_yoni": "Buffalo"},
    1: {"deity": "Yama", "ganam": "Manushya", "symbol": "Female Sexual Organ", "animal_sign": "Elephant", "nadi": "Pitta", "color": "Blood Red", "best_direction": "West", "syllables": "Li, Lu, Le, Lo", "birth_stone": "Diamond", "gender": "Male", "planet": "Shukra", "enemy_yoni": "Lion"},
    2: {"deity": "Agni", "ganam": "Asura", "symbol": "Razor (Axe, sharp edge, or flame)", "animal_sign": "Sheep", "nadi": "Kapha", "color": "White", "best_direction": "North", "syllables": "A, E, U, Ea", "birth_stone": "Ruby", "gender": "Female", "planet": "Ravi", "enemy_yoni": "Monkey"},
    3: {"deity": "Brahma", "ganam": "Manushya", "symbol": "Chariot (An ox cart)", "animal_sign": "Snake", "nadi": "Kapha", "color": "White", "best_direction": "East", "syllables": "O, Va, Vi, Vu", "birth_stone": "Pearl", "gender": "Female", "planet": "Chandra", "enemy_yoni": "Mongoose"},
    4: {"deity": "Moon", "ganam": "Deva", "symbol": "Deer’s Head", "animal_sign": "Snake", "nadi": "Pitta", "color": "Silver Grey", "best_direction": "South", "syllables": "We, Wo, Ka, Ki", "birth_stone": "Coral", "gender": "Female", "planet": "Kuja", "enemy_yoni": "Mongoose"},
    5: {"deity": "Siva", "ganam": "Manushya", "symbol": "Teardrop (The human head)", "animal_sign": "Dog", "nadi": "Vata", "color": "Green", "best_direction": "West", "syllables": "Ku, Gha, Ing, Chh", "birth_stone": "Hessonite", "gender": "Female", "planet": "Rahu", "enemy_yoni": "Deer"},
    6: {"deity": "Aditi", "ganam": "Deva", "symbol": "Bow and a quiver of arrows", "animal_sign": "Cat", "nadi": "Vata", "color": "Lead", "best_direction": "North", "syllables": "Ke, Ko, Ha, Hi", "birth_stone": "Yellow Sapphire", "gender": "Female", "planet": "Guru", "enemy_yoni": "Rat"},
    7: {"deity": "Jupiter", "ganam": "Deva", "symbol": "Flower (The udder of a cow, a circle, an arrow)", "animal_sign": "Sheep", "nadi": "Pitta", "color": "Black Mixed with Red", "best_direction": "East", "syllables": "Hu, He, Ho, Da", "birth_stone": "Blue Sapphire", "gender": "Male", "planet": "Shani", "enemy_yoni": "Monkey"},
    8: {"deity": "Rahu", "ganam": "Asura", "symbol": "Serpent (coiled snake, circle, or wheel)", "animal_sign": "Cat", "nadi": "Kapha", "color": "Black Mixed with Red", "best_direction": "South", "syllables": "De, Du, Da, Do", "birth_stone": "Emerald", "gender": "Male", "planet": "Budha", "enemy_yoni": "Rat"},
    9: {"deity": "Sun", "ganam": "Asura", "symbol": "Palanquin", "animal_sign": "Rat", "nadi": "Kapha", "color": "Cream", "best_direction": "West", "syllables": "Ma, Me, Mu, Me", "birth_stone": "Chrysoberyl", "gender": "Male", "planet": "Ketu", "enemy_yoni": "Cat"},
    10: {"deity": "Aryama", "ganam": "Manushya", "symbol": "Fireplace (Swinging hammock - rest and restoration, front legs of a bed, or a post)", "animal_sign": "Rat", "nadi": "Pitta", "color": "Light Brown", "best_direction": "North", "syllables": "Mo, Ta, Ti, Tu", "birth_stone": "Diamond", "gender": "Female", "planet": "Shukra", "enemy_yoni": "Cat"},
    11: {"deity": "Sun", "ganam": "Manushya", "symbol": "Four Legs Of The Bed (A bed or 2 rear legs of a cot)", "animal_sign": "Cow", "nadi": "Vata", "color": "Bright Blue", "best_direction": "East", "syllables": "Te, To, Pa, Pi", "birth_stone": "Ruby", "gender": "Male", "planet": "Ravi", "enemy_yoni": "Tiger"},
    12: {"deity": "Viswa Karma", "ganam": "Deva", "symbol": "Hand", "animal_sign": "Buffalo", "nadi": "Vata", "color": "Deep Green", "best_direction": "South", "syllables": "Pu, Sha, Na, Tha", "birth_stone": "Pearl", "gender": "Female", "planet": "Chandra", "enemy_yoni": "Horse"},
    13: {"deity": "Vayu", "ganam": "Asura", "symbol": "Pearl", "animal_sign": "Tiger", "nadi": "Pitta", "color": "Black", "best_direction": "West", "syllables": "Pe, Po, Ra, Re", "birth_stone": "Coral", "gender": "Female", "planet": "Kuja", "enemy_yoni": "Cow"},
    14: {"deity": "Indra", "ganam": "Deva", "symbol": "Coral", "animal_sign": "Buffalo", "nadi": "Kapha", "color": "Black", "best_direction": "North", "syllables": "Ru, Re, Ro, Taa", "birth_stone": "Hessonite", "gender": "Male", "planet": "Rahu", "enemy_yoni": "Horse"},
    15: {"deity": "Mitra", "ganam": "Asura", "symbol": "Archway", "animal_sign": "Tiger", "nadi": "Kapha", "color": "Golden", "best_direction": "East", "syllables": "Ti, Tu, Tea, To", "birth_stone": "Yellow Sapphire", "gender": "Male", "planet": "Guru", "enemy_yoni": "Cow"},
    16: {"deity": "Indra", "ganam": "Deva", "symbol": "Lotus", "animal_sign": "Deer", "nadi": "Pitta", "color": "Reddish Brown", "best_direction": "South", "syllables": "Na, Ne, Nu, Ne", "birth_stone": "Blue Sapphire", "gender": "Female", "planet": "Shani", "enemy_yoni": "Dog"},
    17: {"deity": "Niruti", "ganam": "Asura", "symbol": "Earring", "animal_sign": "Deer", "nadi": "Vata", "color": "Cream", "best_direction": "West", "syllables": "No, Ya, Yi, Yu", "birth_stone": "Emerald", "gender": "Male", "planet": "Budha", "enemy_yoni": "Dog"},
    18: {"deity": "Varuna", "ganam": "Asura", "symbol": "Elephant’s Goad (Tied bunch of roots or a lions tail)", "animal_sign": "Dog", "nadi": "Vata", "color": "Brownish Yellow", "best_direction": "North", "syllables": "Ye, Yo, Ba, Be", "birth_stone": "Chrysoberyl", "gender": "Male", "planet": "Ketu", "enemy_yoni": "Deer"},
    19: {"deity": "Viswadeva", "ganam": "Manushya", "symbol": "Elephant’s Tusk", "animal_sign": "Monkey", "nadi": "Pitta", "color": "Black", "best_direction": "East", "syllables": "Bhu, Dha, Pha, Dha", "birth_stone": "Diamond", "gender": "Male", "planet": "Shukra", "enemy_yoni": "Sheep"},
    20: {"deity": "Brahma", "ganam": "Manushya", "symbol": "Planks Of A Bed, Elephant's tusk", "animal_sign": "Mongoose", "nadi": "Kapha", "color": "Copper", "best_direction": "South", "syllables": "Bhe, Bho, Ja, Ji", "birth_stone": "Ruby", "gender": "Male", "planet": "Ravi", "enemy_yoni": "Snake"},
    21: {"deity": "Vishnu", "ganam": "Deva", "symbol": "Earring", "animal_sign": "Monkey", "nadi": "Kapha", "color": "Light Blue", "best_direction": "North", "syllables": "Ju/khi, Je/khu, Jo/khe, Gha/kho", "birth_stone": "Pearl", "gender": "Male", "planet": "Chandra", "enemy_yoni": "Sheep"},
    22: {"deity": "Vasu", "ganam": "Asura", "symbol": "Drum Or Flute", "animal_sign": "Lion", "nadi": "Pitta", "color": "Silver Grey", "best_direction": "East", "syllables": "Ga, Gi, Gu, Ge", "birth_stone": "Coral", "gender": "Female", "planet": "Kuja", "enemy_yoni": "Elephant"},
    23: {"deity": "Varuna", "ganam": "Asura", "symbol": "Hundred Stars (An ox cart, a circle or round charm)", "animal_sign": "Horse", "nadi": "Vata", "color": "Aquamarine", "best_direction": "South", "syllables": "Go, Sa, Si, Su", "birth_stone": "Hessonite", "gender": "Female", "planet": "Rahu", "enemy_yoni": "Buffalo"},
    24: {"deity": "Ajacharana", "ganam": "Manushya", "symbol": "Sword", "animal_sign": "Lion", "nadi": "Vata", "color": "Silver Grey", "best_direction": "West", "syllables": "Se, So, Da, Di", "birth_stone": "Yellow Sapphire", "gender": "Male", "planet": "Guru", "enemy_yoni": "Elephant"},
    25: {"deity": "Ahirbudhanya", "ganam": "Manushya", "symbol": "Twins (Two back legs of a bed)", "animal_sign": "Cow", "nadi": "Pitta", "color": "Purple", "best_direction": "North", "syllables": "Du, Tha, Jha, Da", "birth_stone": "Blue Sapphire", "gender": "Female", "planet": "Shani", "enemy_yoni": "Tiger"},
    26: {"deity": "Poosha", "ganam": "Deva", "symbol": "Fish", "animal_sign": "Elephant", "nadi": "Kapha", "color": "Brown", "best_direction": "East", "syllables": "De, Do, Cha, Chi", "birth_stone": "Emerald", "gender": "Female", "planet": "Budha", "enemy_yoni": "Lion"},
}

assert len(NAKSHATRA_ATTRIBUTES) == len(NAKSHATRAS)
for _index, _row in NAKSHATRA_ATTRIBUTES.items():
    assert tuple(_row) == NAKSHATRA_ATTRIBUTE_FIELDS, _index


def nakshatra_attributes(index: int) -> dict:
    """Reference data for one nakshatra, stamped with where it comes from.

    The block is split in authority: `deity` is BPHS, everything else was
    transcribed from Prokerala. The stamp says so rather than letting the two
    sit side by side looking equally authoritative.
    """
    from . import provenance

    return {
        **NAKSHATRA_ATTRIBUTES[index % len(NAKSHATRAS)],
        **provenance.NAKSHATRA_METADATA,
        "nakshatra_deity_source": provenance.NAKSHATRA_DEITY,
    }
