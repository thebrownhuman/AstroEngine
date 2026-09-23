"""Where the parity suites get their chart from.

By default they call `chart.build()` in this process, which is what you want
when checking the code in the tree. Setting ASTRO_ENGINE_URL sends them over
HTTP to a deployment instead, so the same parity evidence can be gathered
against the thing actually serving traffic:

    ASTRO_ENGINE_URL=http://192.168.68.114:8000 python validation/verify_all.py

The mapping from `BirthData` to the HTTP request is narrower than the dataclass,
because the API deliberately exposes fewer knobs. Rather than silently
approximating, `build_chart` refuses any combination it cannot express exactly
-- a parity suite that quietly compared a slightly different chart would be
worse than one that stops.
"""

from __future__ import annotations

import json
import os
import urllib.request

from astro_engine.chart import BirthData, build
from astro_engine.dasha import DAYS_PER_YEAR, PROKERALA_TRAVERSED_PRECISION

ENGINE_URL = (os.environ.get("ASTRO_ENGINE_URL") or "").rstrip("/") or None

# The API couples the sunrise convention and the dasha rounding behind one
# `prokerala_compatible` flag. BirthData lets them move independently, so only
# these two combinations survive the round trip.
_COMPATIBLE = {
    (None, "apparent"): False,
    (PROKERALA_TRAVERSED_PRECISION, "geometric"): True,
}


def describe() -> str:
    return ENGINE_URL or "in-process"


def _request(path: str, body: dict) -> dict:
    request = urllib.request.Request(
        ENGINE_URL + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(request, timeout=120))


def _as_payload(birth: BirthData) -> dict:
    """Translate a BirthData into the request the API accepts, or refuse."""
    unsupported = []
    if birth.house_system != "P":
        unsupported.append(f"house_system={birth.house_system!r}")
    if birth.equinox != "mean":
        unsupported.append(f"equinox={birth.equinox!r}")
    if birth.dasha_year_length != DAYS_PER_YEAR:
        unsupported.append(f"dasha_year_length={birth.dasha_year_length!r}")

    key = (birth.dasha_traversed_precision, birth.sunrise_convention)
    if key not in _COMPATIBLE:
        unsupported.append(
            f"dasha_traversed_precision={key[0]!r} with "
            f"sunrise_convention={key[1]!r}: the API couples these behind "
            f"prokerala_compatible and cannot express this pair"
        )
    if unsupported:
        raise ValueError(
            "cannot reproduce this chart over HTTP: " + "; ".join(unsupported)
        )

    moment = birth.local_datetime()
    payload = {
        "date": moment.strftime("%Y-%m-%d"),
        "time": moment.strftime("%H:%M:%S"),
        "latitude": birth.latitude,
        "longitude": birth.longitude,
        "ayanamsa": birth.ayanamsa,
        "node_type": birth.node_type,
        "prokerala_compatible": _COMPATIBLE[key],
    }
    if birth.timezone:
        payload["timezone"] = birth.timezone
    return payload


def build_chart(birth: BirthData, vargas=None, dasha_depth: int = 2, **flags) -> dict:
    """The chart, from this process or from a deployment.

    `flags` are the include_* switches, spelled exactly as `chart.build()`
    takes them, so a caller does not have to know which source is in use.
    """
    if ENGINE_URL is None:
        return build(birth, vargas=vargas, dasha_depth=dasha_depth, **flags)

    payload = _as_payload(birth)
    payload["dasha_depth"] = dasha_depth
    if vargas is not None:
        payload["vargas"] = list(vargas)
    payload.update({key: value for key, value in flags.items()
                    if key.startswith("include_")})
    unknown = [key for key in flags if not key.startswith("include_")]
    if unknown:
        raise ValueError(f"cannot pass {unknown} over HTTP")
    return _request("/v1/chart", payload)


def porutham_report(boy: int, boy_pada: int, girl: int, girl_pada: int,
                    twelve: bool = False) -> dict:
    """The Tamil checklist, from this process or from a deployment."""
    if ENGINE_URL is None:
        from astro_engine import porutham
        return porutham.compute(boy, boy_pada, girl, girl_pada, twelve=twelve)
    return _request("/v1/porutham", {
        "boy_nakshatra": boy, "boy_nakshatra_pada": boy_pada,
        "girl_nakshatra": girl, "girl_nakshatra_pada": girl_pada,
        "twelve": twelve,
    })


def muhurta_report(day, latitude: float, longitude: float,
                   utc_offset_hours: float, timezone: str) -> dict:
    """One calendar date's periods, from this process or from a deployment.

    The local call takes a raw UTC offset; the API derives it from an IANA
    zone, so the caller has to supply both and they have to agree.
    """
    if ENGINE_URL is None:
        from astro_engine import muhurta
        return muhurta.compute(day, latitude, longitude, utc_offset_hours)
    return _request("/v1/muhurta", {
        "date": day.strftime("%Y-%m-%d"),
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
    })
