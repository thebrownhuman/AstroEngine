"""BPHS degree-level dignity: exaltation, Moolatrikona and own sign share signs."""

import pytest

from astro_engine.ephemeris import Position, dignity


def at(name, longitude):
    return Position(name, longitude, 0.0, 1.0, int(longitude // 30),
                    longitude % 30, int(longitude // (360 / 27)), 1)


@pytest.mark.parametrize("name, longitude, state, bphs_state", [
    ("Mercury", 150 + 10, "exalted", "exalted"),
    ("Mercury", 150 + 17, "exalted", "moolatrikona"),
    ("Mercury", 150 + 25, "exalted", "own_sign"),
    ("Moon", 30 + 2, "exalted", "exalted"),
    ("Moon", 30 + 10, "exalted", "moolatrikona"),
    ("Sun", 120 + 10, "own_sign", "moolatrikona"),
    ("Sun", 120 + 25, "own_sign", "own_sign"),
    ("Mars", 5, "own_sign", "moolatrikona"),
    ("Mars", 20, "own_sign", "own_sign"),
    ("Jupiter", 240 + 5, "own_sign", "moolatrikona"),
    ("Venus", 180 + 20, "own_sign", "own_sign"),
    ("Saturn", 300 + 10, "own_sign", "moolatrikona"),
    ("Saturn", 270 + 10, "own_sign", "own_sign"),
    ("Sun", 180 + 10, "debilitated", "debilitated"),
    ("Rahu", 30 + 10, "exalted", "exalted"),
])
def test_bphs_state(name, longitude, state, bphs_state):
    result = dignity(name, at(name, longitude), None)
    assert result["state"] == state
    assert result["bphs_state"] == bphs_state
