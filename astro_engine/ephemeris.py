"""Swiss Ephemeris wrapper. Every number in the app originates here."""

from __future__ import annotations

import math
import os
import pathlib
import threading
from dataclasses import dataclass
from datetime import datetime

import swisseph as swe

from .constants import (
    COMBUSTION_ORB, EXALTATION, NAKSHATRAS, NAKSHATRA_LORDS,
    OWN_SIGNS, SIGNS, SIGNS_EN, SIGN_LORDS,
)

AYANAMSA_MODES = {
    "lahiri": swe.SIDM_LAHIRI,
    "lahiri_1940": swe.SIDM_LAHIRI_1940,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "yukteshwar": swe.SIDM_YUKTESHWAR,
    "true_chitra": swe.SIDM_TRUE_CITRA,
    "true_revati": swe.SIDM_TRUE_REVATI,
    "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
}

GRAHAS = [
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mars", swe.MARS),
    ("Mercury", swe.MERCURY),
    ("Jupiter", swe.JUPITER),
    ("Venus", swe.VENUS),
    ("Saturn", swe.SATURN),
]

NAKSHATRA_ARC = 360.0 / 27.0
PADA_ARC = NAKSHATRA_ARC / 4.0

# swisseph's global state (ayanamsa mode, ephemeris path) is process-wide and not
# thread-safe. Serialise every calculation behind one lock.
_SWE_LOCK = threading.Lock()

# Prefer SE_EPHE_PATH, then the ephe/ directory shipped beside this package.
# Falling back to Moshier silently is a trap: it is accurate to about an
# arcsecond rather than a milliarcsecond, which passes every ordinary check
# and then fails the tightest parity sweeps for no visible reason. Finding the
# bundled files without being told means that only happens when they are
# genuinely absent.
BUNDLED_EPHE_PATH = pathlib.Path(__file__).resolve().parent.parent / "ephe"


def _resolve_ephe_path() -> str | None:
    candidates = [os.environ.get("SE_EPHE_PATH"), str(BUNDLED_EPHE_PATH)]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            # A directory with no .se1 files would put swisseph into SWIEPH
            # mode with nothing to read, which errors rather than degrading.
            if any(f.endswith(".se1") for f in os.listdir(candidate)):
                return candidate
    return None


_EPHE_PATH = _resolve_ephe_path()
if _EPHE_PATH:
    swe.set_ephe_path(_EPHE_PATH)
    _BACKEND_FLAG = swe.FLG_SWIEPH
    EPHEMERIS_BACKEND = "swieph"
else:
    # Moshier needs no data files and stays under an arcsecond for
    # 3000 BC - 3000 AD. Good enough to use, not good enough for parity.
    _BACKEND_FLAG = swe.FLG_MOSEPH
    EPHEMERIS_BACKEND = "moshier"

_BASE_FLAGS = _BACKEND_FLAG | swe.FLG_SPEED


@dataclass(frozen=True)
class Position:
    """A single body's sidereal position, fully described."""

    name: str
    longitude: float
    latitude: float
    speed: float
    sign_index: int
    degree_in_sign: float
    nakshatra_index: int
    nakshatra_pada: int

    @property
    def retrograde(self) -> bool:
        return self.speed < 0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "longitude": round(self.longitude, 9),
            "latitude": round(self.latitude, 9),
            "speed": round(self.speed, 6),
            "retrograde": self.retrograde,
            "sign": SIGNS[self.sign_index],
            "sign_en": SIGNS_EN[self.sign_index],
            "sign_index": self.sign_index,
            "degree_in_sign": round(self.degree_in_sign, 9),
            "dms": to_dms(self.degree_in_sign),
            "nakshatra": NAKSHATRAS[self.nakshatra_index],
            "nakshatra_index": self.nakshatra_index,
            "nakshatra_pada": self.nakshatra_pada,
            "nakshatra_lord": NAKSHATRA_LORDS[self.nakshatra_index],
            "sign_lord": SIGN_LORDS[self.sign_index],
        }


def to_dms(degrees: float) -> str:
    total_seconds = round(degrees * 3600)
    d, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{d}°{m:02d}'{s:02d}\""


def julian_day(moment_utc: datetime) -> float:
    hour = (
        moment_utc.hour
        + moment_utc.minute / 60.0
        + moment_utc.second / 3600.0
        + moment_utc.microsecond / 3_600_000_000.0
    )
    return swe.julday(moment_utc.year, moment_utc.month, moment_utc.day, hour, swe.GREG_CAL)


def _describe(name: str, longitude: float, latitude: float, speed: float) -> Position:
    longitude %= 360.0
    nak_index = int(longitude / NAKSHATRA_ARC)
    offset_in_nak = longitude - nak_index * NAKSHATRA_ARC
    return Position(
        name=name,
        longitude=longitude,
        latitude=latitude,
        speed=speed,
        sign_index=int(longitude / 30.0),
        degree_in_sign=longitude % 30.0,
        nakshatra_index=nak_index,
        nakshatra_pada=int(offset_in_nak / PADA_ARC) + 1,
    )


class SiderealSky:
    """Sidereal positions for one instant, in one ayanamsa.

    `equinox` selects which reference the ayanamsa is measured from:

      "mean"  - subtract the nutation-free ayanamsa from the apparent tropical
                longitude. This is what Prokerala and mainstream Indian software
                do, and what published ayanamsa tables are stated against.
                Verified to reproduce Prokerala to 0.001 arcsec.
      "true"  - swisseph's own FLG_SIDEREAL behaviour, which subtracts the
                nutation-included ayanamsa.

    The two differ by the nutation in longitude: an oscillation of +/-17 arcsec
    on an 18.6-year cycle, so it is not a constant you can calibrate away. Mean
    is the default because it is the Jyotisha convention.
    """

    def __init__(
        self,
        jd_ut: float,
        ayanamsa: str = "lahiri",
        node_type: str = "mean",
        equinox: str = "mean",
    ):
        if ayanamsa not in AYANAMSA_MODES:
            raise ValueError(f"unknown ayanamsa {ayanamsa!r}; expected one of {sorted(AYANAMSA_MODES)}")
        if node_type not in ("mean", "true"):
            raise ValueError("node_type must be 'mean' or 'true'")
        if equinox not in ("mean", "true"):
            raise ValueError("equinox must be 'mean' or 'true'")
        self.jd_ut = jd_ut
        self.ayanamsa = ayanamsa
        self.node_type = node_type
        self.equinox = equinox
        # Tropical apparent positions; the ayanamsa is subtracted explicitly so
        # that the choice of reference equinox stays under our control.
        self._flags = _BASE_FLAGS
        self._ayanamsa_flags = _BACKEND_FLAG
        if equinox == "mean":
            self._ayanamsa_flags |= swe.FLG_NONUT

    def _activate(self) -> None:
        swe.set_sid_mode(AYANAMSA_MODES[self.ayanamsa], 0, 0)

    def _ayanamsa_locked(self) -> float:
        """Caller must already hold _SWE_LOCK and have called _activate()."""
        _, value = swe.get_ayanamsa_ex_ut(self.jd_ut, self._ayanamsa_flags)
        return value

    def ayanamsa_value(self) -> float:
        with _SWE_LOCK:
            self._activate()
            return self._ayanamsa_locked()

    def positions(self) -> dict[str, Position]:
        node_body = swe.TRUE_NODE if self.node_type == "true" else swe.MEAN_NODE
        out: dict[str, Position] = {}
        with _SWE_LOCK:
            self._activate()
            ayanamsa = self._ayanamsa_locked()
            for name, body in GRAHAS:
                values, _ = swe.calc_ut(self.jd_ut, body, self._flags)
                out[name] = _describe(name, values[0] - ayanamsa, values[1], values[3])
            node_values, _ = swe.calc_ut(self.jd_ut, node_body, self._flags)
        rahu_lon = node_values[0] - ayanamsa
        rahu_speed = node_values[3]
        out["Rahu"] = _describe("Rahu", rahu_lon, 0.0, rahu_speed)
        out["Ketu"] = _describe("Ketu", rahu_lon + 180.0, 0.0, rahu_speed)
        return out

    def angles(self, latitude: float, longitude: float, house_system: bytes = b"P") -> dict:
        """Ascendant, MC and cusps. Vedic charts use whole-sign houses from the
        Lagna sign, so the cusps are informational only."""
        with _SWE_LOCK:
            self._activate()
            ayanamsa = self._ayanamsa_locked()
            cusps, ascmc = swe.houses_ex(
                self.jd_ut, latitude, longitude, house_system, self._flags
            )
        return {
            "ascendant": _describe("Lagna", ascmc[0] - ayanamsa, 0.0, 0.0),
            "midheaven": _describe("MC", ascmc[1] - ayanamsa, 0.0, 0.0),
            "cusps": [round((c - ayanamsa) % 360.0, 6) for c in cusps],
        }


def dignity(name: str, position: Position, sun_longitude: float | None) -> dict:
    """Classical dignity: exaltation, debilitation, own sign, combustion."""
    state = "neutral"
    exalt = EXALTATION.get(name)
    if exalt is not None:
        exalt_sign, _ = exalt
        if position.sign_index == exalt_sign:
            state = "exalted"
        elif position.sign_index == (exalt_sign + 6) % 12:
            state = "debilitated"
    if state == "neutral" and position.sign_index in OWN_SIGNS.get(name, []):
        state = "own_sign"

    combust = False
    elongation = None
    orb = COMBUSTION_ORB.get(name)
    if orb is not None and sun_longitude is not None:
        separation = abs(position.longitude - sun_longitude) % 360.0
        elongation = min(separation, 360.0 - separation)
        combust = elongation < orb

    return {
        "state": state,
        "combust": combust,
        "elongation_from_sun": round(elongation, 4) if elongation is not None else None,
    }


# Sunrise conventions, in minutes-late order.
#
#   apparent   upper limb with refraction. What you can actually see, and what
#              NOAA-style calculators and published panchangas use. Default.
#   geometric  disc centre, no refraction. What Prokerala uses - verified to the
#              second on three charts. Lands ~4 minutes later than apparent.
#
# The choice matters: a birth in that 4-minute window lands on a different vara.
RISE_CONVENTIONS = {
    "apparent": 0,
    "disc_center": swe.BIT_DISC_CENTER,
    "geometric": swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION,
}
RISE_CONVENTION = "apparent"


def sun_rise_set(
    jd_ut: float,
    latitude: float,
    longitude: float,
    convention: str = RISE_CONVENTION,
) -> dict:
    """Sunrise and sunset bracketing the given instant, as Julian Days (UT).

    The Vedic day (vara) runs sunrise to sunrise, so the civil weekday is wrong
    for anyone born between midnight and sunrise.
    """
    if convention not in RISE_CONVENTIONS:
        raise ValueError(
            f"unknown sunrise convention {convention!r}; "
            f"expected one of {sorted(RISE_CONVENTIONS)}"
        )
    rise_bits = RISE_CONVENTIONS[convention]
    geopos = (longitude, latitude, 0.0)
    flags = _BACKEND_FLAG

    def event(kind: str, after: float, calculation: int) -> float:
        try:
            with _SWE_LOCK:
                result, values = swe.rise_trans(
                    after, swe.SUN, calculation | rise_bits, geopos, 0.0, 0.0, flags,
                )
        except Exception as exc:
            # Swiss Ephemeris raises swisseph.Error for a missing event at
            # circumpolar latitudes instead of returning its documented
            # non-zero result code. Normalize both forms for the API.
            raise ValueError(
                f"no solar {kind} exists for latitude {latitude:.5f}, "
                f"longitude {longitude:.5f}; the location may be in polar "
                "day or polar night"
            ) from exc
        value = values[0] if values else 0.0
        # Swiss Ephemeris reports that no event exists at circumpolar
        # locations through its result code and/or a zero event time. Do not
        # let that sentinel reach revjul(), where it becomes a generic 500.
        if result != 0 or not math.isfinite(value) or value <= 0:
            raise ValueError(
                f"no solar {kind} exists for latitude {latitude:.5f}, "
                f"longitude {longitude:.5f}; the location may be in polar "
                "day or polar night"
            )
        return value

    def next_rise(after: float) -> float:
        return event("rise", after, swe.CALC_RISE)

    def next_set(after: float) -> float:
        return event("set", after, swe.CALC_SET)

    # Walk forward until prev_rise is the sunrise that opens the Vedic day
    # containing jd_ut.
    prev_rise = next_rise(jd_ut - 1.0)
    upcoming = next_rise(prev_rise + 0.1)
    while upcoming <= jd_ut:
        prev_rise = upcoming
        upcoming = next_rise(prev_rise + 0.1)

    # The sunset that belongs to this Vedic day is the first one after its
    # sunrise. Searching from jd_ut - 1 instead returns the previous day's.
    sunset = next_set(prev_rise)

    return {
        "sunrise_jd": prev_rise,
        "next_sunrise_jd": upcoming,
        "sunset_jd": sunset,
    }


def jd_to_datetime(jd_ut: float) -> datetime:
    year, month, day, hours = swe.revjul(jd_ut, swe.GREG_CAL)
    total_seconds = round(hours * 3600, 3)
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    sec = total_seconds % 60
    return datetime(year, month, day, h, m, int(sec), int((sec % 1) * 1_000_000))


class SiderealScanner:
    """Repeated sidereal longitude lookups for one ayanamsa.

    Transit work needs thousands of samples while hunting for sign ingresses and
    returns, so this keeps the flag setup out of the inner loop.
    """

    def __init__(self, ayanamsa: str = "lahiri", equinox: str = "mean"):
        if ayanamsa not in AYANAMSA_MODES:
            raise ValueError(f"unknown ayanamsa {ayanamsa!r}")
        if equinox not in ("mean", "true"):
            raise ValueError("equinox must be 'mean' or 'true'")
        self._mode = AYANAMSA_MODES[ayanamsa]
        self._flags = _BASE_FLAGS
        self._ayanamsa_flags = _BACKEND_FLAG
        if equinox == "mean":
            self._ayanamsa_flags |= swe.FLG_NONUT

    def longitude(self, jd_ut: float, body: int) -> float:
        with _SWE_LOCK:
            swe.set_sid_mode(self._mode, 0, 0)
            _, ayanamsa = swe.get_ayanamsa_ex_ut(jd_ut, self._ayanamsa_flags)
            values, _ = swe.calc_ut(jd_ut, body, self._flags)
        return (values[0] - ayanamsa) % 360.0

    def speed(self, jd_ut: float, body: int) -> float:
        with _SWE_LOCK:
            swe.set_sid_mode(self._mode, 0, 0)
            values, _ = swe.calc_ut(jd_ut, body, self._flags)
        return values[3]
