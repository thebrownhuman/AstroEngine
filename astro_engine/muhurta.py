"""Day-quality periods: choghadiya, hora, and the auspicious and inauspicious
muhurtas of a calendar date.

Everything here divides the interval between sunrise and sunset (or sunset and
the next sunrise) into equal slices, and the only real question is *which*
slice each named period occupies. The texts print weekday tables for that and
the tables disagree with one another, so all of them below were measured: one
sample per weekday against the live API, reading back the exact slice index.
Every measurement landed within 0.002 of a whole slice.

Two different divisions are in play and they are not interchangeable:

  * eighths of the day  -- the kaal periods and the choghadiya
  * fifteenths of the day or night -- the muhurtas, so Abhijit and Dur Muhurat

Note that these are properties of a *calendar date* at a place, not of a birth
instant: Prokerala anchors them to the sunrise of the requested date even when
the requested time falls before it. A birth at 04:30 therefore gets the
choghadiya of the day that is about to begin, not of the Vedic day it is
actually still inside.

Like the upagrahas, the slices only line up with Prokerala under *geometric*
sunrise and sunset.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .ephemeris import jd_to_datetime, julian_day, sun_rise_set

PARTS = 8
MUHURTAS = 15

# The seven choghadiya, in the Chaldean order of their ruling planets:
# Sun, Venus, Mercury, Moon, Saturn, Jupiter, Mars.
CHOGHADIYA = ["Udveg", "Char", "Labh", "Amrut", "Kaal", "Shubh", "Rog"]
CHOGHADIYA_IDS = {name: index for index, name in enumerate(CHOGHADIYA)}
CHOGHADIYA_RULERS = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
CHOGHADIYA_QUALITY = {
    "Udveg": "Inauspicious", "Char": "Good", "Labh": "Most Auspicious",
    "Amrut": "Most Auspicious", "Kaal": "Inauspicious",
    "Shubh": "Most Auspicious", "Rog": "Inauspicious",
}

# The day's first choghadiya is ruled by the lord of the weekday, so its index
# in the cycle above advances three places per weekday. Night begins five
# further on -- and then runs *backwards* through the cycle, two places per
# slot, which no published table mentions and only shows up when you read the
# night list off the live API in time order.
CHOGHADIYA_DAY_STEP = 3
CHOGHADIYA_NIGHT_OFFSET = 5
CHOGHADIYA_DAY_ADVANCE = 1
CHOGHADIYA_NIGHT_ADVANCE = -2

# Eighth of the day each kaal period occupies, indexed by vara (Sunday = 0).
RAHU_KAAL = [7, 1, 6, 4, 5, 3, 2]
YAMAGANDA = [4, 3, 2, 1, 0, 6, 5]
# Gulika is the same eighth the Gulika upagraha is taken from.
GULIKA_KAAL = [(6 - vara) % 7 for vara in range(7)]

# Muhurta of the day (or night) that Dur Muhurat occupies, by vara. Tuesday is
# the only weekday whose second Dur Muhurat falls after sunset.
DUR_MUHURAT = {
    0: [("day", 13)],
    1: [("day", 8), ("day", 11)],
    2: [("day", 3), ("night", 6)],
    3: [("day", 7)],
    4: [("day", 5), ("day", 11)],
    5: [("day", 3), ("day", 8)],
    6: [("day", 2)],
}

# Abhijit is the eighth of the fifteen day muhurtas, the one straddling midday.
ABHIJIT_MUHURTA = 7

# Brahma Muhurat is the second-to-last muhurta before sunrise, measured in
# thirtieths of the whole sunrise-to-sunrise day rather than fifteenths of the
# night. See BRAHMA_RESIDUAL_SECONDS.
BRAHMA_MUHURTAS_BEFORE_SUNRISE = 2

# The three inauspicious choghadiya slots, as slice indices by vara. Kaal Vela
# and Kaal Ratri run mod 7 -- they track a choghadiya *name* -- while Vaar Vela
# runs mod 8 and tracks a slot. Because slots 0 and 7 always share a name,
# Prokerala reports both whenever the computed slot is one of them.
KAAL_VELA = [(4 - CHOGHADIYA_DAY_STEP * vara) % 7 for vara in range(7)]
VAAR_VELA = [(3 + CHOGHADIYA_DAY_STEP * vara) % 8 for vara in range(7)]
KAAL_RATRI = [(5 - 2 * vara) % 7 for vara in range(7)]


def solar_day(
    day: datetime, latitude: float, longitude: float,
    utc_offset_hours: float, convention: str = "geometric",
) -> dict:
    """Sunrise, sunset and next sunrise of one calendar date, in local time."""
    offset = timedelta(hours=utc_offset_hours)
    noon = julian_day(
        datetime.combine(day.date(), datetime.min.time()) + timedelta(hours=12) - offset
    )
    solar = sun_rise_set(noon, latitude, longitude, convention=convention)
    return {
        "sunrise": jd_to_datetime(solar["sunrise_jd"]) + offset,
        "sunset": jd_to_datetime(solar["sunset_jd"]) + offset,
        "next_sunrise": jd_to_datetime(solar["next_sunrise_jd"]) + offset,
    }


def _slices(start: datetime, end: datetime, count: int) -> list[tuple[datetime, datetime]]:
    """Equal slices that tile the span exactly.

    The last boundary is the span end itself rather than start + width * count,
    which microsecond rounding can leave a hair short of it.
    """
    width = (end - start) / count
    edges = [start + width * i for i in range(count)] + [end]
    return list(zip(edges, edges[1:]))


def _period(start: datetime, end: datetime) -> dict:
    return {"start": start.isoformat(), "end": end.isoformat()}


def choghadiya(solar: dict, vara_index: int) -> list[dict]:
    """All sixteen choghadiya of the date, day then night, with their velas."""
    out = []
    for is_day, (start, end) in (
        (True, (solar["sunrise"], solar["sunset"])),
        (False, (solar["sunset"], solar["next_sunrise"])),
    ):
        first = (CHOGHADIYA_DAY_STEP * vara_index) % 7
        if not is_day:
            first = (first + CHOGHADIYA_NIGHT_OFFSET) % 7
        marked = (KAAL_VELA[vara_index], VAAR_VELA[vara_index]) if is_day \
            else (KAAL_RATRI[vara_index],)
        labels = ("Kaal Vela", "Vaar Vela") if is_day else ("Kaal Ratri",)
        # A vela is reported on every slot sharing the marked slot's name, which
        # is why slots 0 and 7 are always flagged together.
        advance = CHOGHADIYA_DAY_ADVANCE if is_day else CHOGHADIYA_NIGHT_ADVANCE
        for slot, (begin, finish) in enumerate(_slices(start, end, PARTS)):
            name = CHOGHADIYA[(first + advance * slot) % 7]
            vela = None
            for label, reference in zip(labels, marked):
                if name == CHOGHADIYA[(first + advance * reference) % 7]:
                    vela = label
            out.append({
                "id": CHOGHADIYA_IDS[name],
                "name": name,
                "ruler": CHOGHADIYA_RULERS[CHOGHADIYA_IDS[name]],
                "type": "Inauspicious" if vela else CHOGHADIYA_QUALITY[name],
                "vela": vela,
                "is_day": is_day,
                "start": begin.isoformat(),
                "end": finish.isoformat(),
            })
    return out


def inauspicious_periods(solar: dict, vara_index: int) -> list[dict]:
    eighths = _slices(solar["sunrise"], solar["sunset"], PARTS)
    day_muhurtas = _slices(solar["sunrise"], solar["sunset"], MUHURTAS)
    night_muhurtas = _slices(solar["sunset"], solar["next_sunrise"], MUHURTAS)

    dur = []
    for span, index in DUR_MUHURAT[vara_index]:
        source = day_muhurtas if span == "day" else night_muhurtas
        dur.append(_period(*source[index]))

    return [
        {"id": 4, "name": "Rahu", "type": "Inauspicious",
         "period": [_period(*eighths[RAHU_KAAL[vara_index]])]},
        {"id": 5, "name": "Yamaganda", "type": "Inauspicious",
         "period": [_period(*eighths[YAMAGANDA[vara_index]])]},
        {"id": 6, "name": "Gulika", "type": "Inauspicious",
         "period": [_period(*eighths[GULIKA_KAAL[vara_index]])]},
        {"id": 7, "name": "Dur Muhurat", "type": "Inauspicious", "period": dur},
    ]


# Brahma Muhurat lands about 23 seconds later in this implementation than in
# Prokerala's, consistently across the samples measured. The duration matches to
# under a second, so the slice width is right and only the anchor is off; no
# sunrise, sunset or ahoratra endpoint on hand reproduces their offset. Reported
# rather than fudged.
BRAHMA_RESIDUAL_SECONDS = 23.5


def auspicious_periods(solar: dict, previous_sunrise: datetime) -> list[dict]:
    day_muhurtas = _slices(solar["sunrise"], solar["sunset"], MUHURTAS)
    abhijit = day_muhurtas[ABHIJIT_MUHURTA]

    # One muhurta here is a thirtieth of the whole sunrise-to-sunrise day, not a
    # fifteenth of the night: the night reading gives a period 6 minutes too long.
    muhurta = (solar["sunrise"] - previous_sunrise) / 30
    brahma_end = solar["sunrise"] - muhurta * (BRAHMA_MUHURTAS_BEFORE_SUNRISE - 1)
    brahma_start = solar["sunrise"] - muhurta * BRAHMA_MUHURTAS_BEFORE_SUNRISE

    return [
        {"id": 1, "name": "Abhijit Muhurat", "type": "Auspicious",
         "period": [_period(*abhijit)]},
        {"id": 3, "name": "Brahma Muhurat", "type": "Auspicious",
         "period": [_period(brahma_start, brahma_end)]},
    ]


# --- hora ---------------------------------------------------------------------

# Horas run in the descending Chaldean order of orbital period, starting with
# the lord of the weekday. Twelve fill the day and twelve the night, so a hora
# is a twelfth of the daylight or of the darkness, not sixty minutes.
HORA_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
HORAS_PER_SPAN = 12
PLANET_IDS = {"Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3,
              "Mars": 4, "Jupiter": 5, "Saturn": 6}
VEDIC_NAMES = {"Sun": "Ravi", "Moon": "Chandra", "Mercury": "Budha",
               "Venus": "Shukra", "Mars": "Kuja", "Jupiter": "Guru",
               "Saturn": "Shani"}

# How good a hora is depends on *both* its own lord and the lord of the day, so
# this is a 7x7 grid rather than a property of the planet. Read off the live API
# one weekday at a time; no relationship scheme in the engine reproduces it --
# the Sun's hora is Good on Sunday and Bad on Friday, while the Moon's is Good
# on Monday and merely Not Bad on Sunday.
HORA_QUALITY = {
    0: {"Sun": "Good", "Moon": "Not Bad", "Mars": "Good",
        "Mercury": "Neither Good Nor Bad", "Jupiter": "Good",
        "Venus": "Not Bad", "Saturn": "Bad"},
    1: {"Sun": "Neither Good Nor Bad", "Moon": "Good",
        "Mars": "Neither Good Nor Bad", "Mercury": "Neither Good Nor Bad",
        "Jupiter": "Neither Good Nor Bad", "Venus": "Neither Good Nor Bad",
        "Saturn": "Bad"},
    2: {"Sun": "Good", "Moon": "Neither Good Nor Bad", "Mars": "Good",
        "Mercury": "Not Bad", "Jupiter": "Good",
        "Venus": "Neither Good Nor Bad", "Saturn": "Bad"},
    3: {"Sun": "Neither Good Nor Bad", "Moon": "Neither Good Nor Bad",
        "Mars": "Bad", "Mercury": "Good",
        "Jupiter": "Neither Good Nor Bad", "Venus": "Good", "Saturn": "Good"},
    4: {"Sun": "Good", "Moon": "Good", "Mars": "Good",
        "Mercury": "Neither Good Nor Bad", "Jupiter": "Good",
        "Venus": "Neither Good Nor Bad", "Saturn": "Neither Good Nor Bad"},
    5: {"Sun": "Bad", "Moon": "Neither Good Nor Bad",
        "Mars": "Neither Good Nor Bad", "Mercury": "Good",
        "Jupiter": "Neither Good Nor Bad", "Venus": "Good", "Saturn": "Good"},
    6: {"Sun": "Bad", "Moon": "Not Bad", "Mars": "Bad", "Mercury": "Good",
        "Jupiter": "Neither Good Nor Bad", "Venus": "Good", "Saturn": "Good"},
}

WEEKDAY_LORDS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def hora(solar: dict, vara_index: int) -> list[dict]:
    """Twenty-four horas, twelve by day and twelve by night."""
    lord = WEEKDAY_LORDS[vara_index]
    position = HORA_ORDER.index(lord)
    quality = HORA_QUALITY[vara_index]

    out = []
    for is_day, (start, end) in (
        (True, (solar["sunrise"], solar["sunset"])),
        (False, (solar["sunset"], solar["next_sunrise"])),
    ):
        for begin, finish in _slices(start, end, HORAS_PER_SPAN):
            ruler = HORA_ORDER[position % 7]
            out.append({
                "hora": {"id": PLANET_IDS[ruler], "name": ruler,
                         "vedic_name": VEDIC_NAMES[ruler]},
                "type": quality[ruler],
                "is_day": is_day,
                "start": begin.isoformat(),
                "end": finish.isoformat(),
            })
            position += 1
    return out


# --- gowri nalla neram --------------------------------------------------------

# The Tamil eight-fold division of the day. Unlike the choghadiya this is not a
# rotation of one cycle: each weekday has its own order, so the grid below is
# the measured table rather than a formula. Ids are Prokerala's.
GOWRI_IDS = {"Dhanam": 0, "Sugam": 1, "Soram": 2, "Visham": 3,
             "Uthi": 4, "Amridha": 5, "Rogam": 6, "Labam": 7}
GOWRI_QUALITY = {
    "Dhanam": "Auspicious", "Sugam": "Auspicious", "Soram": "Inauspicious",
    "Visham": "Inauspicious", "Uthi": "Auspicious", "Amridha": "Auspicious",
    "Rogam": "Inauspicious", "Labam": "Auspicious",
}
GOWRI_DAY = {
    0: ["Uthi", "Amridha", "Rogam", "Labam", "Dhanam", "Sugam", "Soram", "Visham"],
    1: ["Amridha", "Visham", "Rogam", "Labam", "Dhanam", "Sugam", "Soram", "Uthi"],
    2: ["Rogam", "Labam", "Dhanam", "Sugam", "Soram", "Uthi", "Visham", "Amridha"],
    3: ["Labam", "Dhanam", "Sugam", "Soram", "Visham", "Uthi", "Amridha", "Rogam"],
    4: ["Dhanam", "Sugam", "Soram", "Uthi", "Amridha", "Visham", "Rogam", "Labam"],
    5: ["Sugam", "Soram", "Uthi", "Visham", "Amridha", "Rogam", "Labam", "Dhanam"],
    6: ["Soram", "Uthi", "Visham", "Amridha", "Rogam", "Labam", "Dhanam", "Sugam"],
}
# Night repeats the same weekday row, rotated. The rotation alternates between
# four and five places and does not follow from anything else here, so it too is
# measured.
GOWRI_NIGHT_ROTATION = {0: 4, 1: 5, 2: 4, 3: 5, 4: 4, 5: 5, 6: 5}

# On Saturday night Prokerala's own last slot repeats Soram instead of closing
# the row with Rogam, contradicting the rotation its other seven slots follow
# and every other weekday. The coherent value is emitted here, so this engine
# and their API disagree on exactly one of the 112 gowri slots.
GOWRI_KNOWN_DEVIATION = "Saturday night slot 8"


def gowri_nalla_neram(solar: dict, vara_index: int) -> list[dict]:
    day_row = GOWRI_DAY[vara_index]
    turn = GOWRI_NIGHT_ROTATION[vara_index]
    night_row = day_row[turn:] + day_row[:turn]

    out = []
    for is_day, row, (start, end) in (
        (True, day_row, (solar["sunrise"], solar["sunset"])),
        (False, night_row, (solar["sunset"], solar["next_sunrise"])),
    ):
        for name, (begin, finish) in zip(row, _slices(start, end, PARTS)):
            out.append({
                "id": GOWRI_IDS[name],
                "name": name,
                "type": GOWRI_QUALITY[name],
                "is_day": is_day,
                "start": begin.isoformat(),
                "end": finish.isoformat(),
            })
    return out


# --- disha shool --------------------------------------------------------------

# The direction not to travel in, its remedy, and how long the prohibition runs.
# The directions follow the classical pairing; the remedies and durations were
# measured. Durations are whole ninety-six-minute muhurtas of a mean civil day,
# not of the actual daylight, which is why they do not move with the season.
DISHA_SHOOL_MUHURTA_SECONDS = 5760
DISHA_SHOOL = {
    0: ("West", "Jaggery", 3),
    1: ("East", "Curd", 2),
    2: ("North", "Milk", 3),
    3: ("North", "Milk", 4),
    4: ("South", "Oil", 5),
    5: ("West", "Jaggery", 3),
    6: ("East", "Curd", 2),
}


def disha_shool(solar: dict, vara_index: int) -> dict:
    direction, remedy, muhurtas = DISHA_SHOOL[vara_index]
    start = solar["sunrise"]
    end = start + timedelta(seconds=DISHA_SHOOL_MUHURTA_SECONDS * muhurtas)
    return {"direction": direction, "remedy": remedy,
            "start": start.isoformat(), "end": end.isoformat()}


def compute(
    day: datetime, latitude: float, longitude: float, utc_offset_hours: float,
    convention: str = "geometric",
) -> dict:
    """Every period of one calendar date at one place."""
    solar = solar_day(day, latitude, longitude, utc_offset_hours, convention)
    previous = solar_day(day - timedelta(days=1), latitude, longitude,
                         utc_offset_hours, convention)
    # The vara is the weekday the sunrise falls on.
    vara_index = (solar["sunrise"].weekday() + 1) % 7

    return {
        "date": day.date().isoformat(),
        "vara_index": vara_index,
        "sunrise": solar["sunrise"].isoformat(),
        "sunset": solar["sunset"].isoformat(),
        "next_sunrise": solar["next_sunrise"].isoformat(),
        "choghadiya": choghadiya(solar, vara_index),
        "inauspicious": inauspicious_periods(solar, vara_index),
        "auspicious": auspicious_periods(solar, previous["sunrise"]),
        "hora": hora(solar, vara_index),
        "gowri_nalla_neram": gowri_nalla_neram(solar, vara_index),
        "disha_shool": disha_shool(solar, vara_index),
    }
