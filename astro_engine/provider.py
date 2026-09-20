"""AstrologyProvider: the seam between the engine and the application.

The app stores a chart once and reopens it forever, so what matters here is not
speed but durability:

  * every record carries a SCHEMA_VERSION and an ENGINE_VERSION, so a stored row
    can always be read back and you can tell what produced it;
  * `inputs_hash` fingerprints the birth details and the calculation conventions
    together, so you can detect when a stored chart no longer matches what the
    current engine would produce;
  * the record is plain JSON-serialisable data, ready for a Postgres jsonb
    column with no adapter of its own.

The interface exists so the calculation source can be swapped. `LocalEngine` is
the built-in implementation; a `ProkeralaProvider` could sit beside it without
the rest of the app noticing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Protocol

from . import numerology as num
from . import yogas as yg
from .chart import ENGINE_VERSION, BirthData, build, summarise
from .places import resolve

SCHEMA_VERSION = 1

# Divisional charts worth storing by default. D1 and D9 carry most of the
# interpretive weight; D10 is career, D12 parents, D30 misfortune.
DEFAULT_VARGAS = ("D1", "D9", "D10", "D12", "D30")


@dataclass(frozen=True)
class BirthDetails:
    """What the user types on the sign-up form."""

    date_of_birth: str                  # YYYY-MM-DD, local to the birth place
    time_of_birth: str                  # HH:MM or HH:MM:SS, 24h, local
    place: str | None = None            # resolved offline if coordinates absent
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None         # IANA; derived from coordinates if absent
    full_name: str | None = None        # only needed for numerology

    def moment(self) -> datetime:
        return datetime.fromisoformat(f"{self.date_of_birth}T{self.time_of_birth}")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Conventions:
    """Calculation choices. Stored with the chart because they change results.

    Defaults are the astronomically correct readings. Set `prokerala_compatible`
    to reproduce Prokerala's output exactly, including the two places their
    implementation is wrong (see numerology.py and dasha.py).
    """

    ayanamsa: str = "lahiri"
    node_type: str = "mean"
    equinox: str = "mean"
    sunrise_convention: str = "apparent"
    dasha_year_length: float = 365.25
    dasha_traversed_precision: int | None = None
    prokerala_compatible: bool = False

    def resolved(self) -> "Conventions":
        if not self.prokerala_compatible:
            return self
        return Conventions(
            ayanamsa=self.ayanamsa,
            node_type=self.node_type,
            equinox="mean",
            sunrise_convention="geometric",
            dasha_year_length=365.25,
            dasha_traversed_precision=num_precision(),
            prokerala_compatible=True,
        )

    def as_dict(self) -> dict:
        return asdict(self)


def num_precision() -> int:
    from .dasha import PROKERALA_TRAVERSED_PRECISION

    return PROKERALA_TRAVERSED_PRECISION


@dataclass
class ChartRecord:
    """One row in your charts table."""

    schema_version: int
    engine_version: str
    provider: str
    computed_at: str
    inputs: dict
    conventions: dict
    inputs_hash: str
    resolved_place: dict | None
    chart: dict
    yogas: dict | None = None
    transits: dict | None = None
    numerology: dict | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "ChartRecord":
        return cls(**json.loads(payload))

    def is_stale(self) -> bool:
        """True when the current engine would produce something different.

        Cheap guard for a migration: recompute from `inputs` and compare hashes
        rather than diffing whole charts.
        """
        return (
            self.schema_version != SCHEMA_VERSION
            or self.engine_version != ENGINE_VERSION
        )


def fingerprint(inputs: dict, conventions: dict) -> str:
    """Stable hash over the birth details and the conventions together.

    Both matter: the same birth data under a different ayanamsa is a different
    chart, and silently serving one for the other is the bug this prevents.
    """
    payload = json.dumps(
        {"inputs": inputs, "conventions": conventions,
         "schema": SCHEMA_VERSION, "engine": ENGINE_VERSION},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


class AstrologyProvider(Protocol):
    """Swap-in point for the calculation source."""

    name: str

    def compute(self, birth: BirthDetails, conventions: Conventions) -> ChartRecord:
        ...


class LocalEngine:
    """Swiss Ephemeris, in-process. No network, no API key, no rate limit."""

    name = "astro_engine.local"

    def __init__(
        self,
        vargas: tuple[str, ...] = DEFAULT_VARGAS,
        dasha_depth: int = 2,
        include_yogas: bool = True,
        include_transits: bool = True,
        include_extras: bool = True,
    ):
        self.vargas = list(vargas)
        self.dasha_depth = dasha_depth
        self.include_yogas = include_yogas
        self.include_transits = include_transits
        # Ashtakavarga, upagrahas, planetary friendship and the doshas. Cheap
        # to compute and awkward to add to a chart already in the database.
        self.include_extras = include_extras

    def compute(
        self,
        birth: BirthDetails,
        conventions: Conventions | None = None,
        reference_time: datetime | None = None,
    ) -> ChartRecord:
        conventions = (conventions or Conventions()).resolved()
        warnings: list[str] = []

        latitude, longitude = birth.latitude, birth.longitude
        timezone_name = birth.timezone
        resolved_place = None
        if latitude is None or longitude is None:
            if not birth.place:
                raise ValueError("supply either `place`, or latitude and longitude")
            found = resolve(birth.place)
            latitude, longitude = found.latitude, found.longitude
            timezone_name = timezone_name or found.timezone
            resolved_place = found.as_dict()
            if found.population < 5000:
                warnings.append(
                    f"'{birth.place}' resolved to a small settlement "
                    f"({found.label}); confirm it is the intended place"
                )

        moment = birth.moment()
        data = BirthData(
            year=moment.year, month=moment.month, day=moment.day,
            hour=moment.hour, minute=moment.minute, second=moment.second,
            latitude=latitude, longitude=longitude, timezone=timezone_name,
            ayanamsa=conventions.ayanamsa, node_type=conventions.node_type,
            equinox=conventions.equinox,
            sunrise_convention=conventions.sunrise_convention,
            dasha_year_length=conventions.dasha_year_length,
            dasha_traversed_precision=conventions.dasha_traversed_precision,
        )
        chart = build(
            data,
            vargas=self.vargas,
            dasha_depth=self.dasha_depth,
            reference_time=reference_time,
            include_transits=self.include_transits,
            include_ashtakavarga=self.include_extras,
            include_upagrahas=self.include_extras,
            include_relationships=self.include_extras,
            include_doshas=self.include_extras,
        )

        if chart["engine"]["ephemeris"] == "moshier":
            warnings.append(
                "running on the Moshier fallback; set SE_EPHE_PATH for full "
                "0.001 arcsec precision"
            )
        if chart["solar_day"]["born_before_sunrise"]:
            warnings.append(
                "born before sunrise: the Vedic vara is the previous day's "
                "(panchanga.vara), not the calendar weekday"
            )

        transit_block = chart.pop("transits", None)
        numerology_block = None
        if birth.full_name:
            parts = birth.full_name.split()
            numerology_block = num.report(
                num.Name(parts[0], " ".join(parts[1:-1]) if len(parts) > 2 else "",
                         parts[-1] if len(parts) > 1 else ""),
                date.fromisoformat(birth.date_of_birth),
                prokerala_compatible=conventions.prokerala_compatible,
            )

        inputs = birth.as_dict()
        return ChartRecord(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            provider=self.name,
            computed_at=datetime.now(timezone.utc).isoformat(),
            inputs=inputs,
            conventions=conventions.as_dict(),
            inputs_hash=fingerprint(inputs, conventions.as_dict()),
            resolved_place=resolved_place,
            chart=chart,
            yogas=yg.report(chart) if self.include_yogas else None,
            transits=transit_block,
            numerology=numerology_block,
            warnings=warnings,
        )


# --- read helpers, the shape the chat tools want -----------------------------

def get_planet_details(record: ChartRecord, planet: str) -> dict:
    """Everything about one graha, flattened for an LLM to quote directly."""
    grahas = record.chart["grahas"]
    match = next((k for k in grahas if k.lower() == planet.lower()), None)
    if match is None:
        raise KeyError(f"unknown graha {planet!r}; expected one of {sorted(grahas)}")

    graha = grahas[match]
    house = next(h for h in record.chart["houses"] if h["house"] == graha["house"])
    aspects = next(a for a in record.chart["aspects"] if a["graha"] == match)
    vargas = {
        key: {"sign": block["grahas"][match]["sign"]["name_en"],
              "house": block["grahas"][match]["house"]}
        for key, block in record.chart["vargas"].items()
    }
    return {
        "graha": match,
        "sign": graha["sign_en"],
        "degree": graha["dms"],
        "house": graha["house"],
        "house_significations": house["significations"],
        "nakshatra": graha["nakshatra"],
        "nakshatra_pada": graha["nakshatra_pada"],
        "nakshatra_lord": graha["nakshatra_lord"],
        "retrograde": graha["retrograde"],
        "dignity": graha["dignity"],
        "nature": graha["nature"],
        "aspects_houses": aspects["aspects_houses"],
        "aspects_grahas": aspects["aspects_grahas"],
        "divisional_placements": vargas,
    }


def get_chart_summary(record: ChartRecord) -> dict:
    """The small payload a dashboard needs, without the whole chart."""
    chart = record.chart
    return {
        "lagna": {
            "sign": chart["lagna"]["sign_en"],
            "degree": chart["lagna"]["dms"],
            "nakshatra": chart["lagna"]["nakshatra"],
            "pada": chart["lagna"]["nakshatra_pada"],
        },
        "moon_sign": chart["grahas"]["Moon"]["sign_en"],
        "sun_sign": chart["grahas"]["Sun"]["sign_en"],
        "nakshatra": chart["panchanga"]["nakshatra"]["name"],
        "grahas": {
            name: {"sign": g["sign_en"], "house": g["house"], "degree": g["dms"],
                   "retrograde": g["retrograde"], "dignity": g["dignity"]["state"]}
            for name, g in chart["grahas"].items()
        },
        "current_dasha": chart["current_dasha"]["chain"],
        "yogas_present": (record.yogas or {}).get("present", []),
        "text": summarise(chart),
    }
