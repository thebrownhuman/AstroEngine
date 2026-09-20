"""Hit every endpoint on a running server and report what answered.

A health check says the process is up; this says the engine behind it works.
Each endpoint is called with a realistic body and one field of the response is
pulled out and printed, so a wrong-but-200 answer is visible rather than
hidden behind a status code.

    python examples/smoke_api.py
    python examples/smoke_api.py --url http://127.0.0.1:8000

Exit code is 0 only if every endpoint answered and every probe found its
field.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

DELHI = {"date": "1990-01-15", "time": "04:30", "place": "Delhi"}
MUMBAI = {"date": "1992-06-20", "time": "10:15", "place": "Mumbai"}

# (method, path, body, probe) -- probe pulls one telling value out of the
# response so the line printed is evidence, not just a status code.
CHECKS = [
    ("GET", "/health", None, lambda d: d.get("status", "ok")),
    ("POST", "/v1/chart", DELHI,
     lambda d: f"{d['lagna']['sign']} lagna, Moon in {d['grahas']['Moon']['sign']}"),
    ("POST", "/v1/chart/summary", DELHI,
     lambda d: f"{len(d['summary'].splitlines())} lines"),
    ("POST", "/v1/yogas", DELHI,
     lambda d: f"{d['yogas']['total_present']} present"),
    ("POST", "/v1/transits", DELHI,
     lambda d: "sade sati "
               + (d['transits']['sade_sati']['current_phase'] or "not running")),
    ("POST", "/v1/ashtakavarga", DELHI,
     lambda d: f"sarva total {d['sarvashtakavarga']['total']}"),
    ("POST", "/v1/upagrahas", DELHI,
     lambda d: f"{len(d['upagrahas'])} upagrahas"),
    ("POST", "/v1/doshas", DELHI,
     lambda d: f"papasamyam {d['doshas']['papasamyam']['total_points']} points"),
    ("POST", "/v1/relationships", DELHI,
     lambda d: f"{len(d['planet_relationship']['natural_relationship'])} bodies"),
    ("POST", "/v1/sudarshana", DELHI,
     lambda d: f"ritu {d['drik_ritu']['name']}"),
    ("POST", "/v1/bala", DELHI,
     lambda d: f"{len(d['tara_bala'])} tara windows"),
    ("POST", "/v1/nakshatra", DELHI,
     lambda d: f"{d['nakshatra']['name']}, deity {d['additional_info']['deity']}"),
    ("POST", "/v1/muhurta", {"date": "1990-01-15", "place": "Delhi"},
     lambda d: f"{len(d['inauspicious'])} inauspicious periods"),
    ("POST", "/v1/numerology",
     {"first_name": "Shivansh", "last_name": "Mishra",
      "date_of_birth": "1990-01-15"},
     lambda d: f"{len(d['pythagorean'])} pythagorean, "
               f"{len(d['chaldean'])} chaldean numbers"),
    ("POST", "/v1/kp", DELHI,
     lambda d: f"cusp 1 sub lord {d['houses'][0]['sub_lord']}"),
    ("POST", "/v1/matching", {"boy": DELHI, "girl": MUMBAI},
     lambda d: f"{d['guna_milan']['total_points']}/"
               f"{d['guna_milan']['maximum_points']} guna"),
    ("POST", "/v1/porutham",
     {"boy_nakshatra": 7, "boy_nakshatra_pada": 1,
      "girl_nakshatra": 13, "girl_nakshatra_pada": 2, "twelve": True},
     lambda d: f"{d['obtained_points']}/{d['maximum_points']}, "
               f"{d['verified_points']}/{d['verified_maximum']} verified"),
    ("GET", "/v1/places?q=Delhi&limit=5", None,
     lambda d: f"{d['count']} matches, first {d['results'][0]['name']}"),
    ("GET", "/v1/timezone?latitude=28.61&longitude=77.21"
            "&date=1990-01-15&time=04:30", None,
     lambda d: d["timezone"]),
    ("GET", "/v1/tool-definition", None, lambda d: d["name"]),
    ("GET", "/v1/tool-definitions", None,
     lambda d: f"{len(d)} tools"),
]


def call(base: str, method: str, path: str, body: dict | None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    options = parser.parse_args()
    base = options.url.rstrip("/")

    print(f"{base}\n")
    failures = 0
    for method, path, body, probe in CHECKS:
        label = f"{method:4} {path:22}"
        try:
            payload = call(base, method, path, body)
        except urllib.error.HTTPError as exc:
            print(f"  {label} HTTP {exc.code}  {exc.read()[:120].decode(errors='replace')}")
            failures += 1
            continue
        except Exception as exc:                          # noqa: BLE001
            print(f"  {label} unreachable: {str(exc)[:80]}")
            failures += 1
            continue
        try:
            detail = probe(payload)
        except Exception as exc:                          # noqa: BLE001
            # A 200 with the wrong shape is a failure worth seeing.
            print(f"  {label} 200 but unreadable: {type(exc).__name__} {exc}")
            failures += 1
            continue
        print(f"  {label} ok   {detail}")

    print()
    if failures:
        print(f"{len(CHECKS) - failures}/{len(CHECKS)} endpoints healthy, "
              f"{failures} failed")
        return 1
    print(f"all {len(CHECKS)} endpoints healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
