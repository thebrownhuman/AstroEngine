"""Ad-hoc probe: fetch one endpoint and print it, using the shared cache.

    python validation/probe.py upagraha-position
    python validation/probe.py kaal-sarp-dosha --chart="Chennai 2003"

Everything goes through `against_prokerala.fetch`, so a probe is paid for once
and then free forever. Extra query parameters are passed as `key=value`.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

sys.path.insert(0, ".")
from validation.against_prokerala import fetch  # noqa: E402

CHARTS = {
    "Delhi 1990": (datetime(1990, 1, 15, 4, 30), 28.6139, 77.2090, "+05:30"),
    "Mumbai 1975": (datetime(1975, 8, 22, 17, 45), 19.0760, 72.8777, "+05:30"),
    "Chennai 2003": (datetime(2003, 3, 7, 9, 5), 13.0827, 80.2707, "+05:30"),
    "London 1988": (datetime(1988, 11, 2, 23, 20), 51.5074, -0.1278, "+00:00"),
}


def params_for(label: str) -> dict:
    moment, lat, lon, tz = CHARTS[label]
    return {
        "ayanamsa": 1,
        "coordinates": f"{lat},{lon}",
        "datetime": moment.strftime("%Y-%m-%dT%H:%M:%S") + tz,
    }


def main(argv: list[str]) -> int:
    endpoint = argv[0]
    label = "Delhi 1990"
    extra = {}
    for arg in argv[1:]:
        key, _, value = arg.lstrip("-").partition("=")
        if key == "chart":
            label = value
        else:
            extra[key] = value
    payload = fetch(endpoint, {**params_for(label), **extra})
    print(json.dumps(payload["data"], indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
