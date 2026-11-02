"""Dates are read in the proleptic Gregorian calendar. Before the 1582 reform
most records were kept in the Julian calendar, so such charts carry a warning
rather than silently shifting the birth by ten or more days."""
import pytest

from astro_engine.chart import BirthData, build


def _chart(y, m, d):
    return build(BirthData(y, m, d, 12, 0, 0, 41.9, 12.5, "Europe/Rome"))


@pytest.mark.parametrize("ymd", [(1500, 3, 1), (1582, 10, 4)])
def test_pre_reform_date_warns(ymd):
    assert any("Gregorian" in w and "Julian" in w for w in _chart(*ymd)["warnings"])


def test_dropped_reform_days_warn():
    assert any("never existed" in w for w in _chart(1582, 10, 10)["warnings"])


def test_post_reform_date_has_no_calendar_warning():
    assert not any("Gregorian" in w for w in _chart(1582, 10, 15).get("warnings", []))
