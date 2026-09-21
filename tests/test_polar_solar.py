from unittest.mock import patch

import pytest

from astro_engine.ephemeris import sun_rise_set


def test_sun_rise_set_rejects_missing_solar_event():
    """Circumpolar Swiss-Ephemeris sentinels become a clear domain error."""

    def no_event(*args, **kwargs):
        return -2, (0.0,)

    with patch("astro_engine.ephemeris.swe.rise_trans", side_effect=no_event):
        with pytest.raises(ValueError, match="no solar rise exists"):
            sun_rise_set(2460483.0, 69.6492, 18.9553)


def test_sun_rise_set_normalizes_backend_exception():
    with patch(
        "astro_engine.ephemeris.swe.rise_trans",
        side_effect=RuntimeError("backend has no event"),
    ):
        with pytest.raises(ValueError, match="no solar rise exists"):
            sun_rise_set(2460483.0, 69.6492, 18.9553)
