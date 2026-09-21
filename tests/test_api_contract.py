import pytest
from fastapi import HTTPException

from astro_engine import api


def test_location_alternatives_are_visible_in_openapi_and_tool_schemas():
    openapi = api.app.openapi()
    for name in ("ChartRequest", "DayRequest"):
        schema = openapi["components"]["schemas"][name]
        assert schema["oneOf"] == [
            {"required": ["place"]},
            {"required": ["latitude", "longitude"]},
        ]

    assert api.tool_definition()["input_schema"]["oneOf"] == [
        {"required": ["place"]},
        {"required": ["latitude", "longitude"]},
    ]
    muhurta = next(
        tool for tool in api.tool_definitions() if tool["name"] == "get_muhurta"
    )
    assert "timezone" in muhurta["input_schema"]["properties"]
    assert muhurta["input_schema"]["oneOf"] == [
        {"required": ["place"]},
        {"required": ["latitude", "longitude"]},
    ]


def test_muhurta_turns_solar_event_failure_into_422(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("no solar rise exists")

    monkeypatch.setattr(api.day_periods, "compute", fail)
    monkeypatch.setattr(
        api,
        "_day_location",
        lambda request: (
            28.6,
            77.2,
            "Asia/Kolkata",
            __import__("datetime").datetime(2024, 1, 15, 12),
            {"utc_offset_hours": 5.5},
        ),
    )
    request = api.DayRequest(
        date="2024-01-15", latitude=28.6, longitude=77.2, timezone="Asia/Kolkata"
    )

    with pytest.raises(HTTPException) as error:
        api.muhurta_report(request)

    assert error.value.status_code == 422
    assert error.value.detail == "no solar rise exists"


def test_chart_turns_missing_place_data_into_503(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError("places database is unavailable")

    monkeypatch.setattr(api, "build", fail)
    request = api.ChartRequest(
        date="2024-01-15", time="12:00", latitude=28.6, longitude=77.2,
        timezone="Asia/Kolkata",
    )

    with pytest.raises(HTTPException) as error:
        api.chart(request)

    assert error.value.status_code == 503
    assert error.value.detail == "places database is unavailable"


def test_chart_normalizes_offset_aware_reference_time():
    request = api.ChartRequest(
        date="1990-01-15", time="04:30", latitude=28.6, longitude=77.2,
        timezone="Asia/Kolkata", reference_time="2024-01-15T06:30:00Z",
        vargas=["D1"], dasha_depth=1,
    )

    result = api.chart(request)

    assert result["current_dasha"]["as_of"] == "2024-01-15T12:00:00"


def test_muhurta_rejects_an_unknown_timezone_as_422():
    request = api.DayRequest(
        date="2024-01-15", latitude=28.6, longitude=77.2, timezone="Not/AZone"
    )

    with pytest.raises(HTTPException) as error:
        api.muhurta_report(request)

    assert error.value.status_code == 422


def test_location_and_personal_day_inputs_are_not_silently_ignored():
    with pytest.raises(ValueError, match="not both"):
        api.ChartRequest(
            date="2024-01-15", time="12:00", place="Delhi", latitude=28.6
        )

    with pytest.raises(ValueError, match="janma_nakshatra"):
        api.PersonalDayRequest(
            date="2024-01-15", latitude=28.6, longitude=77.2,
            timezone="Asia/Kolkata", janma_nakshatra=0,
        )
