"""Offline place-name lookup, built from GeoNames.

Users type "Delhi", not "28.6139, 77.2090". This resolves a name to coordinates
and an IANA timezone with no network call and no API key, which keeps the whole
stack free and working offline.

Build the index once:

    python -m astro_engine.places build

Then queries are a few milliseconds against a local SQLite FTS5 index.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(os.environ.get("ASTRO_DATA_DIR", "data"))
INDEX_PATH = DATA_DIR / "places.sqlite"

# GeoNames dumps to ingest. Country files give village-level detail; the cities
# file gives worldwide coverage. Later sources win on duplicate geonameid.
SOURCES = ("cities5000.txt", "IN.txt")

# GeoNames feature codes worth keeping. P = populated place; the ADM codes are
# administrative areas. Everything else (mountains, rivers, hotels) is noise.
KEEP_CLASSES = {"P"}
KEEP_ADMIN_CODES = {"ADM1", "ADM2", "ADM3"}

# Search tiers, best first. A settlement beats a tehsil beats a district beats a
# state: nobody is born in "Uttar Pradesh", they are born in a town.
TIER = {"P": 0, "ADM3": 1, "ADM2": 2, "ADM1": 3}

# Columns in the GeoNames tab-separated dump.
COL_ID, COL_NAME, COL_ASCII, COL_ALT = 0, 1, 2, 3
COL_LAT, COL_LON = 4, 5
COL_CLASS, COL_CODE, COL_COUNTRY = 6, 7, 8
COL_ADMIN1 = 10
COL_POPULATION = 14
COL_TIMEZONE = 17

MAX_ALTERNATE_NAMES = 12


@dataclass(frozen=True)
class Place:
    name: str
    admin1: str
    country: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str
    population: int
    kind: str = "city"

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        parts.append(self.country)
        return ", ".join(parts)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "admin1": self.admin1,
            "country": self.country,
            "country_code": self.country_code,
            "label": self.label,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "population": self.population,
            "kind": self.kind,
        }


def _fold(text: str) -> str:
    """Strip accents so 'Pune' matches 'Puné' and 'Bengaluru' matches typing."""
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(c for c in stripped if not unicodedata.combining(c)).lower()


def _load_lookup(path: Path, key_col: int, value_col: int, skip_comments: bool) -> dict:
    table: dict[str, str] = {}
    if not path.exists():
        return table
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if skip_comments and line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) > max(key_col, value_col):
                table[fields[key_col]] = fields[value_col]
    return table


def build_index(data_dir: Path = DATA_DIR, index_path: Path | None = None) -> Path:
    """Ingest the GeoNames dumps into a searchable SQLite index."""
    index_path = index_path or (data_dir / "places.sqlite")
    admin1 = _load_lookup(data_dir / "admin1CodesASCII.txt", 0, 1, skip_comments=False)
    countries = _load_lookup(data_dir / "countryInfo.txt", 0, 4, skip_comments=True)

    if index_path.exists():
        index_path.unlink()
    connection = sqlite3.connect(index_path)
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        CREATE TABLE place (
            geonameid  INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            admin1     TEXT NOT NULL,
            country    TEXT NOT NULL,
            cc         TEXT NOT NULL,
            latitude   REAL NOT NULL,
            longitude  REAL NOT NULL,
            timezone   TEXT NOT NULL,
            population INTEGER NOT NULL,
            kind       TEXT NOT NULL,
            tier       INTEGER NOT NULL,
            folded     TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE place_fts USING fts5(
            search, content=''
        );
        """
    )

    seen: set[int] = set()
    rows: list[tuple] = []
    documents: list[tuple] = []

    for source in SOURCES:
        path = data_dir / source
        if not path.exists():
            print(f"  skipping {source} (not present)")
            continue
        kept = 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                f = line.rstrip("\n").split("\t")
                if len(f) <= COL_TIMEZONE:
                    continue
                feature_class, feature_code = f[COL_CLASS], f[COL_CODE]
                if feature_class not in KEEP_CLASSES and feature_code not in KEEP_ADMIN_CODES:
                    continue
                geonameid = int(f[COL_ID])
                if geonameid in seen:
                    continue
                seen.add(geonameid)

                country_code = f[COL_COUNTRY]
                admin_key = f"{country_code}.{f[COL_ADMIN1]}"
                names = [f[COL_NAME], f[COL_ASCII]]
                names += f[COL_ALT].split(",")[:MAX_ALTERNATE_NAMES]

                rows.append((
                    geonameid,
                    f[COL_NAME],
                    admin1.get(admin_key, ""),
                    countries.get(country_code, country_code),
                    country_code,
                    float(f[COL_LAT]),
                    float(f[COL_LON]),
                    f[COL_TIMEZONE],
                    int(f[COL_POPULATION] or 0),
                    "city" if feature_class in KEEP_CLASSES else "admin",
                    TIER["P"] if feature_class in KEEP_CLASSES else TIER[feature_code],
                    _fold(f[COL_NAME]),
                ))
                unique = {_fold(n) for n in names if n}
                documents.append((geonameid, " ".join(sorted(unique))))
                kept += 1
        print(f"  {source}: kept {kept:,}")

    rows = _enrich_populations(rows)
    connection.executemany("INSERT INTO place VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    connection.executemany("INSERT INTO place_fts(rowid, search) VALUES (?,?)", documents)
    connection.commit()
    connection.execute("VACUUM")
    connection.close()
    print(f"  indexed {len(rows):,} places -> {index_path} "
          f"({index_path.stat().st_size / 1e6:.1f} MB)")
    return index_path


# Row layout used while building, mirroring the place table.
R_NAME, R_ADMIN1, R_LAT, R_LON, R_POP, R_TIER, R_FOLDED = 1, 2, 5, 6, 8, 10, 11

# A tehsil's population only transfers to a settlement essentially co-located
# with it. Uttar Pradesh has dozens of villages called Sultanpur; only the one
# beside Sultanpur tehsil is the Sultanpur people mean.
ENRICH_RADIUS_DEGREES = 0.1  # roughly 11 km


def _enrich_populations(rows: list[tuple]) -> list[tuple]:
    """Give a settlement the population of the tehsil it sits inside.

    GeoNames often records an Indian town's population against its ADM3 tehsil
    and leaves the P record at zero - Ballia town is 0 while Ballia tehsil is
    979,400. Without this a real town ranks below any namesake hamlet; with it
    applied too broadly, every namesake hamlet inherits the same number. So the
    population goes to the single nearest same-named settlement, and only if it
    is close enough to plausibly be the same place.
    """
    candidates: dict[tuple[str, str], list[int]] = {}
    populated: dict[tuple[str, str], list[tuple]] = {}
    for index, row in enumerate(rows):
        if row[R_TIER] != TIER["P"]:
            continue
        key = (row[R_FOLDED], row[R_ADMIN1])
        if row[R_POP] == 0:
            candidates.setdefault(key, []).append(index)
        else:
            populated.setdefault(key, []).append(row)

    enriched = list(rows)
    for row in rows:
        if row[R_TIER] != TIER["ADM3"] or row[R_POP] == 0:
            continue
        nearby = candidates.get((row[R_FOLDED], row[R_ADMIN1]))
        if not nearby:
            continue
        # If a same-named settlement already carries a real population, the
        # tehsil figure belongs to that one and must not be handed to a
        # zero-population namesake down the road.
        if any(
            other[R_POP] > 0
            and (other[R_LAT] - row[R_LAT]) ** 2 + (other[R_LON] - row[R_LON]) ** 2
            < ENRICH_RADIUS_DEGREES ** 2
            for other in populated.get((row[R_FOLDED], row[R_ADMIN1]), ())
        ):
            continue
        best_index, best_distance = None, ENRICH_RADIUS_DEGREES ** 2
        for index in nearby:
            other = enriched[index]
            distance = (other[R_LAT] - row[R_LAT]) ** 2 + (other[R_LON] - row[R_LON]) ** 2
            if distance < best_distance:
                best_index, best_distance = index, distance
        if best_index is None:
            continue
        winner = enriched[best_index]
        if winner[R_POP] < row[R_POP]:
            enriched[best_index] = winner[:R_POP] + (row[R_POP],) + winner[R_POP + 1:]
    return enriched


_connection: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                f"place index missing at {INDEX_PATH}. "
                "Build it with: python -m astro_engine.places build"
            )
        _connection = sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True,
                                      check_same_thread=False)
    return _connection


def _escape(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def search(query: str, limit: int = 8, country: str | None = None) -> list[Place]:
    """Find places matching a free-text name, most prominent first.

    Ranked by population, because someone typing "Delhi" means the city of 11
    million, not a hamlet that shares the name.
    """
    terms = [t for t in _fold(query).replace(",", " ").split() if t]
    if not terms:
        return []
    # Prefix-match the last token so partial typing works.
    expression = " AND ".join(
        [_escape(t) for t in terms[:-1]] + [_escape(terms[-1]) + "*"]
    )

    # Rank by tier then population: someone typing "Sultanpur" means the town,
    # not the 3.8-million-person district containing it. An exact name match
    # outranks a prefix match regardless of tier.
    folded_query = " ".join(terms)
    sql = """
        SELECT p.name, p.admin1, p.country, p.cc, p.latitude, p.longitude,
               p.timezone, p.population, p.kind
        FROM place_fts JOIN place p ON p.geonameid = place_fts.rowid
        WHERE place_fts MATCH ?
    """
    params: list = [expression]
    if country:
        sql += " AND p.cc = ?"
        params.append(country.upper())
    sql += """
        ORDER BY (p.folded = ?) DESC,
                 p.tier ASC,
                 p.population DESC,
                 p.name
        LIMIT ?
    """
    params.extend([folded_query, limit])

    try:
        rows = _connect().execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    return [Place(*row) for row in rows]


def resolve(query: str, country: str | None = None) -> Place:
    """Best single match, or raise with the alternatives that were considered."""
    matches = search(query, limit=5, country=country)
    if not matches:
        raise ValueError(f"no place found matching {query!r}")
    return matches[0]


def _main(argv: list[str]) -> int:
    # Windows consoles default to cp1252 and choke on names like "Vārānasi".
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(argv) > 1 and argv[1] == "build":
        print("Building place index from GeoNames dumps...")
        build_index()
        return 0
    if len(argv) > 1:
        for place in search(" ".join(argv[1:])):
            print(f"{place.label:<55} {place.latitude:>10.4f} {place.longitude:>11.4f}  "
                  f"{place.timezone:<22} pop {place.population:,}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
