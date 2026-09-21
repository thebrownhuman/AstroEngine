"""FastAPI surface for the astrology engine.

Stateless and deterministic: same input always yields the same JSON. Designed to
sit behind a Cloudflare Tunnel and be called as a tool by an LLM.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .chart import ENGINE_VERSION, BirthData, build, summarise
from .dasha import PROKERALA_TRAVERSED_PRECISION
from .ephemeris import AYANAMSA_MODES, EPHEMERIS_BACKEND, julian_day
from . import bala as strength
from . import kp as krishnamurti
from . import matching as milan
from . import muhurta as day_periods
from . import numerology as num
from . import provenance
from . import porutham as tamil_match
from . import yogas as yg
from .geo import timezone_for, to_utc
from .places import resolve, search
from .vargas import VARGAS

app = FastAPI(
    title="astro_engine",
    version=ENGINE_VERSION,
    description=(
        "Deterministic sidereal (Vedic) astrology calculations on Swiss Ephemeris. "
        "Returns raw chart data for an LLM to interpret."
    ),
)


def _build_http_error(exc: Exception) -> HTTPException:
    """Map expected chart-build failures to stable API status codes."""
    status_code = 503 if isinstance(exc, FileNotFoundError) else 422
    return HTTPException(status_code=status_code, detail=str(exc))


class ChartRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {"required": ["place"]},
                {"required": ["latitude", "longitude"]},
            ],
        }
    )

    date: str = Field(..., description="Local birth date, YYYY-MM-DD", examples=["1990-01-15"])
    time: str = Field(..., description="Local birth time, HH:MM or HH:MM:SS", examples=["04:30"])
    place: str | None = Field(
        None,
        description=(
            "Birth place by name, e.g. 'Sultanpur, Uttar Pradesh' or 'London'. "
            "Resolved offline against GeoNames. Supply this OR latitude/longitude."
        ),
        examples=["Delhi"],
    )
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone: str | None = Field(
        None,
        description="IANA name. Omit to derive it from the coordinates.",
        examples=["Asia/Kolkata"],
    )
    ayanamsa: str = Field("lahiri", description=f"One of: {', '.join(sorted(AYANAMSA_MODES))}")
    node_type: Literal["mean", "true"] = "mean"
    vargas: list[str] = Field(
        default_factory=lambda: ["D1", "D9", "D10", "D12", "D30"],
        description=f"Divisional charts to include. Available: {', '.join(VARGAS)}",
    )
    dasha_depth: int = Field(2, ge=1, le=4, description="1=maha, 2=+antar, 3=+pratyantar")
    prokerala_compatible: bool = Field(
        False,
        description=(
            "Reproduce Prokerala's output exactly. Switches three conventions at "
            "once: geometric sunrise (disc centre, no refraction - about 4 minutes "
            "later than real sunrise, and it can move the vara), and the 3-decimal "
            "rounding of the nakshatra traversal fraction that shifts their dasha "
            "boundaries by up to ~1.5 days. Leave it off for the astronomically "
            "correct values."
        ),
    )
    include_yogas: bool = Field(
        False,
        description=(
            "Add yoga detection: 18 yogas verified identical to Prokerala, "
            "2 weakly verified, 1 unverified, plus 3 extras including Mangal "
            "dosha. Every yoga reports its own parity status."
        ),
    )
    include_transits: bool = Field(
        False,
        description=(
            "Add the gochara block: current transits, every Sade Sati cycle with "
            "exact phase dates, Dhaiyya and Ashtama Shani periods, and Jupiter "
            "and Saturn returns."
        ),
    )
    include_ashtakavarga: bool = Field(
        False,
        description=(
            "Add the bindu tables: each graha's bhinnashtakavarga with its "
            "trikona and ekaadhipatya reductions, plus sarvashtakavarga."
        ),
    )
    include_upagrahas: bool = Field(
        False,
        description=(
            "Add the eleven upagrahas. The six time-derived ones (Gulika, Mandi, "
            "Kala, Mrityu, Ardha Prahara, Yamaghanta) depend on the sunrise "
            "convention, so set prokerala_compatible to match Prokerala."
        ),
    )
    include_relationships: bool = Field(
        False,
        description="Add natural, temporal and compound planetary friendship tables.",
    )
    include_doshas: bool = Field(
        False, description="Add Kaal Sarpa / Kaal Amrita and the papasamyam grid.",
    )
    include_calendar: bool = Field(
        False,
        description=(
            "Add the ayana, the drik ritu, and the Sudarshana Chakra -- the "
            "chart counted from the Lagna, the Sun and the Moon in turn."
        ),
    )
    include_nakshatra_info: bool = Field(
        False,
        description=(
            "Add the janma nakshatra's reference block -- deity, ganam, "
            "symbol, animal sign, nadi, colour, direction, syllables, birth "
            "stone, gender, ruling planet and enemy yoni."
        ),
    )
    reference_time: datetime | None = Field(
        None, description="Instant used for 'current dasha' and transits. Defaults to now."
    )

    @model_validator(mode="after")
    def _needs_a_location(self):
        has_place = self.place is not None
        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        if has_place and (has_latitude or has_longitude):
            raise ValueError("supply either `place`, or both `latitude` and `longitude`, not both")
        if not has_place and not (has_latitude and has_longitude):
            raise ValueError("supply either `place`, or both `latitude` and `longitude`")
        return self

    def location(self) -> tuple[float, float, str | None, dict | None]:
        """Coordinates plus the resolved place, when a name was given."""
        if self.latitude is not None and self.longitude is not None:
            return self.latitude, self.longitude, self.timezone, None
        found = resolve(self.place)
        return (
            found.latitude,
            found.longitude,
            self.timezone or found.timezone,
            found.as_dict(),
        )

    @field_validator("ayanamsa")
    @classmethod
    def _known_ayanamsa(cls, value: str) -> str:
        if value not in AYANAMSA_MODES:
            raise ValueError(f"unknown ayanamsa {value!r}")
        return value

    @field_validator("vargas")
    @classmethod
    def _known_vargas(cls, value: list[str]) -> list[str]:
        unknown = [v for v in value if v not in VARGAS]
        if unknown:
            raise ValueError(f"unknown vargas: {unknown}")
        return value

    def to_birth_data(self) -> BirthData:
        try:
            moment = datetime.fromisoformat(f"{self.date}T{self.time}")
        except ValueError as exc:
            raise ValueError(f"could not parse date/time: {exc}") from exc
        latitude, longitude, timezone, _ = self.location()
        return BirthData(
            year=moment.year, month=moment.month, day=moment.day,
            hour=moment.hour, minute=moment.minute, second=moment.second,
            latitude=latitude, longitude=longitude,
            timezone=timezone, ayanamsa=self.ayanamsa, node_type=self.node_type,
            dasha_traversed_precision=(
                PROKERALA_TRAVERSED_PRECISION if self.prokerala_compatible else None
            ),
            sunrise_convention="geometric" if self.prokerala_compatible else "apparent",
        )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": ENGINE_VERSION,
        "ephemeris": EPHEMERIS_BACKEND,
        "ayanamsas": sorted(AYANAMSA_MODES),
        "vargas": list(VARGAS),
        "source_vocabulary": provenance.SOURCE_MEANINGS,
    }


@app.post("/v1/chart")
def chart(request: ChartRequest) -> dict:
    try:
        data = build(
            request.to_birth_data(),
            vargas=request.vargas,
            dasha_depth=request.dasha_depth,
            reference_time=request.reference_time,
            include_transits=request.include_transits,
            include_ashtakavarga=request.include_ashtakavarga,
            include_upagrahas=request.include_upagrahas,
            include_relationships=request.include_relationships,
            include_doshas=request.include_doshas,
            include_calendar=request.include_calendar,
            include_nakshatra_info=request.include_nakshatra_info,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    if request.include_yogas:
        data["yogas"] = yg.report(data)
    resolved = request.location()[3]
    if resolved:
        data["input"]["place"] = resolved
    return data


@app.post("/v1/chart/summary")
def chart_summary(request: ChartRequest) -> dict:
    """Token-cheap text rendering, for stuffing into a prompt directly."""
    try:
        data = build(
            request.to_birth_data(),
            vargas=request.vargas,
            dasha_depth=1,
            reference_time=request.reference_time,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"summary": summarise(data), "engine": data["engine"], "input": data["input"]}


@app.post("/v1/yogas")
def yoga_report(request: ChartRequest) -> dict:
    """Yoga detection only, with the evidence behind each verdict."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"engine": data["engine"], "input": data["input"],
            "lagna": data["lagna"], "yogas": yg.report(data)}


@app.post("/v1/transits")
def transits(request: ChartRequest) -> dict:
    """Gochara only: Sade Sati, Dhaiyya, Ashtama Shani, returns, live positions."""
    try:
        data = build(
            request.to_birth_data(),
            vargas=["D1"],
            dasha_depth=1,
            reference_time=request.reference_time,
            include_transits=True,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {
        "engine": data["engine"],
        "input": data["input"],
        "natal_moon": data["grahas"]["Moon"],
        "transits": data["transits"],
        **provenance.TRANSIT,
    }


@app.post("/v1/ashtakavarga")
def ashtakavarga_report(request: ChartRequest) -> dict:
    """Bindu tables only: seven bhinnashtakavargas plus sarvashtakavarga."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1,
                     include_ashtakavarga=True)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"engine": data["engine"], "input": data["input"], "lagna": data["lagna"],
            "ashtakavarga": data["ashtakavarga"],
            "ashtakavarga_source": data["ashtakavarga_source"],
            "sarvashtakavarga": data["sarvashtakavarga"]}


@app.post("/v1/upagrahas")
def upagraha_report(request: ChartRequest) -> dict:
    """The eleven upagrahas, sun-derived and time-derived."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1,
                     include_upagrahas=True)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"engine": data["engine"], "input": data["input"],
            "solar_day": data["solar_day"], "upagrahas": data["upagrahas"]}


@app.post("/v1/doshas")
def dosha_report(request: ChartRequest) -> dict:
    """Kaal Sarpa / Kaal Amrita, papasamyam, and Mangal dosha."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1,
                     include_doshas=True)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {
        "engine": data["engine"], "input": data["input"],
        "doshas": {**data["doshas"], "mangal_dosha": yg.kuja(yg.ChartView(data)).as_dict()},
    }


@app.post("/v1/nakshatra")
def nakshatra_report(request: ChartRequest) -> dict:
    """The janma nakshatra with its full reference block."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1,
                     include_nakshatra_info=True)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    moon = data["grahas"]["Moon"]
    return {
        "engine": data["engine"], "input": data["input"],
        "nakshatra": {
            "index": moon["nakshatra_index"], "name": moon["nakshatra"],
            "pada": moon["nakshatra_pada"], "lord": moon["nakshatra_lord"],
        },
        "additional_info": data["nakshatra_info"],
    }


@app.post("/v1/sudarshana")
def sudarshana_report(request: ChartRequest) -> dict:
    """The chart read three times: from the Lagna, the Sun and the Moon."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1,
                     include_calendar=True)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"engine": data["engine"], "input": data["input"],
            "solstice": data["solstice"], "drik_ritu": data["drik_ritu"],
            "sudarshana_chakra": data["sudarshana_chakra"]}


@app.post("/v1/relationships")
def relationship_report(request: ChartRequest) -> dict:
    """Natural, temporal and compound planetary friendship."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1,
                     include_relationships=True)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"engine": data["engine"], "input": data["input"],
            "planet_relationship": data["planet_relationship"]}



class MatchRequest(BaseModel):
    """Two births. Only the Moon matters, but a full chart is built for each."""

    boy: ChartRequest
    girl: ChartRequest


@app.post("/v1/matching")
def matching_report(request: MatchRequest) -> dict:
    """Ashtakoot guna milan out of thirty-six."""
    try:
        boy = build(request.boy.to_birth_data(), vargas=["D1"], dasha_depth=1)
        girl = build(request.girl.to_birth_data(), vargas=["D1"], dasha_depth=1)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return milan.compute(boy, girl)


class PoruthamRequest(BaseModel):
    boy_nakshatra: int = Field(..., ge=0, le=26, description="0 = Ashwini")
    boy_nakshatra_pada: int = Field(..., ge=1, le=4)
    girl_nakshatra: int = Field(..., ge=0, le=26)
    girl_nakshatra_pada: int = Field(..., ge=1, le=4)
    twelve: bool = Field(
        False, description="Add Nadi and Varna for the thirumana list of twelve."
    )


@app.post("/v1/porutham")
def porutham_report(request: PoruthamRequest) -> dict:
    """The Tamil compatibility checklist.

    All twelve checks reproduce Prokerala exactly -- 648/648 measured -- so
    every entry carries `"parity": "verified"` and `verified_points` now equals
    `obtained_points`. Both pairs are kept for API compatibility.

    These are provider-compatible tables, not BPHS: several were recovered by
    measurement because their classical forms fit only part of the grid.
    """
    return tamil_match.compute(
        request.boy_nakshatra, request.boy_nakshatra_pada,
        request.girl_nakshatra, request.girl_nakshatra_pada,
        twelve=request.twelve,
    )


class DayRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {"required": ["place"]},
                {"required": ["latitude", "longitude"]},
            ],
        }
    )

    date: str = Field(..., description="Local date, YYYY-MM-DD", examples=["1990-01-15"])
    place: str | None = Field(None, examples=["Delhi"])
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone: str | None = None

    @model_validator(mode="after")
    def _needs_a_location(self):
        has_place = self.place is not None
        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        if has_place and (has_latitude or has_longitude):
            raise ValueError("supply either `place`, or both `latitude` and `longitude`, not both")
        if not has_place and not (has_latitude and has_longitude):
            raise ValueError("supply either `place`, or both `latitude` and `longitude`")
        return self


def _day_location(request: DayRequest) -> tuple[float, float, str | None, datetime, dict]:
    """Resolve a calendar request once and return its UTC provenance."""
    latitude, longitude = request.latitude, request.longitude
    timezone = request.timezone
    if latitude is None or longitude is None:
        found = resolve(request.place)
        latitude, longitude = found.latitude, found.longitude
        timezone = timezone or found.timezone
    moment = datetime.fromisoformat(f"{request.date}T12:00:00")
    _, tz_info = to_utc(moment, latitude, longitude, timezone)
    return latitude, longitude, timezone, moment, tz_info


@app.post("/v1/muhurta")
def muhurta_report(request: DayRequest) -> dict:
    """Choghadiya, hora, the kaal periods, Abhijit, Brahma and disha shool.

    These belong to a calendar date at a place, not to a birth instant.
    """
    try:
        latitude, longitude, _, moment, tz_info = _day_location(request)
        return day_periods.compute(
            moment, latitude, longitude, tz_info["utc_offset_hours"]
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class PersonalDayRequest(DayRequest):
    janma_nakshatra: int | None = Field(
        None, ge=0, le=26, description="Natal Moon nakshatra, 0 = Ashwini."
    )
    janma_rasi: int | None = Field(
        None, ge=0, le=11, description="Natal Moon sign, 0 = Mesha."
    )

    @model_validator(mode="after")
    def _natal_inputs_are_a_pair(self):
        if (self.janma_nakshatra is None) != (self.janma_rasi is None):
            raise ValueError("supply both `janma_nakshatra` and `janma_rasi`, or neither")
        return self


@app.post("/v1/bala")
def bala_report(request: PersonalDayRequest) -> dict:
    """Tara bala, chandra bala and chandrashtama for one date.

    Supply janma_nakshatra and janma_rasi for a personal verdict; without them
    you get the windows and which natal positions each one favours.

    Parity: these two endpoints were never checked against Prokerala -- the
    credits ran out first -- so the rules here are the classical ones and the
    block says so.
    """
    try:
        latitude, longitude, _, moment, tz_info = _day_location(request)
        found = strength.day(moment, tz_info["utc_offset_hours"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    found["parity"] = strength.PARITY

    if request.janma_nakshatra is not None and request.janma_rasi is not None:
        from swisseph import MOON

        transit = strength.SiderealScanner()
        jd = julian_day(moment - timedelta(hours=tz_info["utc_offset_hours"]))
        longitude_now = transit.longitude(jd, MOON)
        found["for_person"] = strength.for_person(
            request.janma_nakshatra, request.janma_rasi,
            int(longitude_now / strength.NAKSHATRA_ARC), int(longitude_now / 30.0),
        )
    return found


@app.post("/v1/kp")
def kp_report(request: ChartRequest) -> dict:
    """Krishnamurti Paddhati: Placidus cusps, sub lords and significators."""
    try:
        data = build(request.to_birth_data(), vargas=["D1"], dasha_depth=1)
    except (ValueError, FileNotFoundError) as exc:
        raise _build_http_error(exc) from exc
    return {"engine": data["engine"], "input": data["input"],
            **krishnamurti.compute(data, data["cusps"][:12])}


class NumerologyRequest(BaseModel):
    first_name: str = Field(..., examples=["John"])
    middle_name: str = Field("", examples=[""])
    last_name: str = Field(..., examples=["Doe"])
    date_of_birth: str = Field(..., description="YYYY-MM-DD", examples=["2004-02-12"])
    reference_date: str | None = Field(
        None, description="For personal/universal cycles. Defaults to today."
    )
    additional_vowel: bool = Field(
        False, description="Treat Y and W as vowels for soul urge and personality."
    )
    prokerala_compatible: bool = Field(
        False,
        description=(
            "Reproduce two quirks in Prokerala's implementation: their Universal "
            "Day and Chaldean Life Path both drop the year. Everything else "
            "already matches them exactly."
        ),
    )


@app.post("/v1/numerology")
def numerology(request: NumerologyRequest) -> dict:
    """Full Pythagorean and Chaldean report in one call."""
    try:
        birth = date.fromisoformat(request.date_of_birth)
        reference = (
            date.fromisoformat(request.reference_date) if request.reference_date else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"bad date: {exc}") from exc

    return num.report(
        num.Name(request.first_name, request.middle_name, request.last_name),
        birth,
        reference=reference,
        additional_vowel=request.additional_vowel,
        prokerala_compatible=request.prokerala_compatible,
    )


@app.get("/v1/places")
def places(q: str, limit: int = 8, country: str | None = None) -> dict:
    """Search birth places by name. Offline, no API key, no rate limit."""
    try:
        matches = search(q, limit=limit, country=country)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"query": q, "count": len(matches), "results": [m.as_dict() for m in matches]}


@app.get("/v1/timezone")
def resolve_timezone(latitude: float, longitude: float) -> dict:
    try:
        return {"timezone": timezone_for(latitude, longitude)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/tool-definition")
def tool_definition() -> dict:
    """Anthropic tool-use schema, so the LLM can call this service directly."""
    return {
        "name": "get_vedic_chart",
        "description": (
            "Compute an exact sidereal (Vedic) birth chart from birth date, time and "
            "place. Returns planetary positions, houses, divisional charts, panchanga "
            "and the Vimshottari dasha timeline. Always call this before interpreting "
            "a chart; never estimate positions yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Local birth date, YYYY-MM-DD"},
                "time": {"type": "string", "description": "Local birth time, HH:MM (24h)"},
                "place": {
                    "type": "string",
                    "description": (
                        "Birth place by name, e.g. 'Sultanpur, Uttar Pradesh'. "
                        "Use this unless you were given exact coordinates."
                    ),
                },
                "latitude": {"type": "number", "description": "Birth latitude in degrees"},
                "longitude": {"type": "number", "description": "Birth longitude in degrees"},
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone. Omit to derive from coordinates.",
                },
                "include_transits": {
                    "type": "boolean",
                    "description": (
                        "Set true when the question involves timing, current "
                        "periods, Sade Sati, or what is happening now."
                    ),
                },
                "include_yogas": {
                    "type": "boolean",
                    "description": (
                        "Set true when the question is about the strengths and "
                        "combinations in the chart rather than raw positions."
                    ),
                },
                "include_ashtakavarga": {
                    "type": "boolean",
                    "description": (
                        "Set true when the question is about which houses or "
                        "signs are strong, or asks for bindu counts."
                    ),
                },
                "include_doshas": {
                    "type": "boolean",
                    "description": (
                        "Set true for questions about Kaal Sarpa, Mangal dosha "
                        "or affliction generally."
                    ),
                },
                "include_upagrahas": {
                    "type": "boolean",
                    "description": (
                        "Set true when Gulika, Mandi or the other sub-planets "
                        "are asked about. Needs prokerala_compatible."
                    ),
                },
                "include_relationships": {
                    "type": "boolean",
                    "description": (
                        "Set true when the question turns on which planets are "
                        "friends or enemies in this chart."
                    ),
                },
                "prokerala_compatible": {
                    "type": "boolean",
                    "description": (
                        "Match Prokerala's conventions exactly instead of the "
                        "astronomically correct ones. Required for the upagrahas."
                    ),
                },
                "vargas": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(VARGAS)},
                    "description": "Divisional charts to include.",
                },
            },
            "required": ["date", "time"],
            "oneOf": [
                {"required": ["place"]},
                {"required": ["latitude", "longitude"]},
            ],
        },
    }


@app.get("/v1/tool-definitions")
def tool_definitions() -> list[dict]:
    """Every endpoint as an Anthropic tool, for wiring up a chat agent.

    The chart tool covers most questions; the rest are here so a model can
    reach compatibility, muhurta and KP without a second round trip.
    """
    birth = tool_definition()["input_schema"]
    return [
        tool_definition(),
        {
            "name": "get_kundli_matching",
            "description": (
                "Ashtakoot guna milan between two births, scored out of 36. "
                "Use for marriage compatibility questions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"boy": birth, "girl": birth},
                "required": ["boy", "girl"],
            },
        },
        {
            "name": "get_muhurta",
            "description": (
                "The auspicious and inauspicious periods of one calendar date "
                "at one place: choghadiya, hora, Rahu Kaal, Abhijit. Use when "
                "asked when to do something, not about a birth."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Local date, YYYY-MM-DD"},
                    "place": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone; omit to derive it from the coordinates or place.",
                    },
                },
                "required": ["date"],
                "oneOf": [
                    {"required": ["place"]},
                    {"required": ["latitude", "longitude"]},
                ],
            },
        },
        {
            "name": "get_kp_chart",
            "description": (
                "Krishnamurti Paddhati: Placidus cusps, star and sub lords, "
                "and house significators. Use only when KP is asked for by name."
            ),
            "input_schema": birth,
        },
    ]
