"""Local birth time -> UTC.

This is the single most common source of wrong charts. India alone has had
Bombay/Calcutta local time, IST at +5:30 from 1906, and wartime DST in 1942-45.
zoneinfo carries the full IANA history, so we never hardcode an offset.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@lru_cache(maxsize=1)
def _finder():
    from timezonefinder import TimezoneFinder

    return TimezoneFinder()


def timezone_for(latitude: float, longitude: float) -> str:
    name = _finder().timezone_at(lat=latitude, lng=longitude)
    if name is None:
        name = _finder().closest_timezone_at(lat=latitude, lng=longitude)
    if name is None:
        raise ValueError(
            f"could not resolve a timezone for ({latitude}, {longitude}); "
            "pass `timezone` explicitly"
        )
    return name


def to_utc(
    local_time: datetime,
    latitude: float,
    longitude: float,
    timezone: str | None = None,
) -> tuple[datetime, dict]:
    """Returns the UTC instant plus provenance describing how we got there."""
    if local_time.tzinfo is not None:
        raise ValueError("pass a naive local datetime; the timezone is resolved separately")

    resolved = timezone or timezone_for(latitude, longitude)
    try:
        zone = ZoneInfo(resolved)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone {resolved!r}") from exc

    aware = local_time.replace(tzinfo=zone)
    offset = aware.utcoffset()
    dst = aware.dst()
    if offset is None:
        raise ValueError(f"timezone {resolved!r} produced no UTC offset for {local_time}")

    return aware.astimezone(ZoneInfo("UTC")).replace(tzinfo=None), {
        "timezone": resolved,
        "timezone_source": "explicit" if timezone else "derived_from_coordinates",
        "utc_offset_hours": offset.total_seconds() / 3600.0,
        "dst_active": bool(dst and dst.total_seconds()),
        "local_time": local_time.isoformat(),
    }
