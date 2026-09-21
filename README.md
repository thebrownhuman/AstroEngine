# astro_engine

A self-hosted Vedic astrology engine that reproduces Prokerala's API output,
built on Swiss Ephemeris. No API key, no credits, no rate limit, works offline.

Every number it returns has been checked against the live Prokerala API or, for
the raw astronomy, against NASA JPL Horizons. Where it disagrees, it says so —
see [Parity](#parity).

```bash
python -m uvicorn astro_engine.api:app --host 127.0.0.1 --port 8000
```

```bash
curl -X POST http://127.0.0.1:8000/v1/chart -H "Content-Type: application/json" -d "{\"date\":\"1990-01-15\",\"time\":\"04:30\",\"place\":\"Delhi\",\"prokerala_compatible\":true,\"include_yogas\":true,\"include_transits\":true,\"include_ashtakavarga\":true,\"include_upagrahas\":true,\"include_doshas\":true,\"include_relationships\":true}"
```

---

## The one flag that matters

`prokerala_compatible` switches the engine from *astronomically correct* to
*bit-identical to Prokerala*. It changes three conventions together:

| | default (`false`) | `prokerala_compatible: true` |
|---|---|---|
| Sunrise | apparent — upper limb, with refraction | geometric — disc centre, no refraction |
| Dasha traversal | full precision | rounded to 3 decimals |
| Numerology | standard | Universal Day and Chaldean Life Path drop the year |

For a Delhi 1990-01-15 04:30 birth:

```
prokerala_compatible=false   sunrise 07:14:50   Venus maha ends 2004-07-31 08:43:01
prokerala_compatible=true    sunrise 07:19:15   Venus maha ends 2004-07-30 22:08:24
Prokerala's own answer       sunrise 07:19:16   Venus maha ends 2004-07-30 22:08:23
```

The residual second is their rounding. The four-minute sunrise difference is
real and it matters: a birth inside that window falls on a different vara.

Several features **only** match under `prokerala_compatible`, because they are
built on sunrise: the six time-derived upagrahas, and everything in
`/v1/muhurta`.

---

## What it computes

### Birth chart
Planetary longitudes, Lagna, whole-sign houses, Placidus cusps, nakshatra and
pada, retrogradation, dignity, combustion, graha drishti, panchanga (tithi,
nakshatra, yoga, karana, vara), sunrise and sunset.

### Divisional charts
Sixteen vargas — D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30,
D40, D45, D60. Twelve of them verified placement-for-placement.

### Dasha
Vimshottari to pratyantardasha, with the balance at birth.

### Transits
Every Sade Sati cycle with exact phase dates, Dhaiyya, Ashtama Shani, Kantaka
Shani, and Jupiter and Saturn returns. Sign ingresses bisected to one second.

### Ashtakavarga
All seven bhinnashtakavarga tables, sarvashtakavarga, and both reductions —
trikona shodhana and ekadhipatya shodhana.

### Upagrahas
All eleven: Dhuma, Vyatipata, Parivesha, Indrachapa, Upaketu, Kala, Mrityu,
Ardha Prahara, Yamaghanta, Gulika, Mandi.

### Yogas and doshas
Twenty-four yogas including the five Panchamahapurusha, Kaal Sarpa and Kaal
Amrita with all twelve type names, Mangal dosha, and the papasamyam grid.

### Relationships
Naisargika, tatkalika and panchadha maitri across all ten bodies.

### Muhurta
Choghadiya with velas, twenty-four horas, Rahu Kaal, Yamaganda, Gulika Kaal,
Dur Muhurat, Abhijit, Brahma Muhurat, Gowri Nalla Neram, Disha Shool.

### Compatibility
Ashtakoot guna milan out of thirty-six, and the Tamil porutham checklist.

### KP
Placidus cusps, star / sub / sub-sub lords for every point, and the four levels
of house significator.

### Sudarshana Chakra
The same chart read from the Lagna, the Sun and the Moon, plus the ayana and
the drik ritu.

### Personal day strength
Tara bala, chandra bala and chandrashtama, either for one natal Moon or as the
windows of a date with the natal positions each one favours. Both daily tables
reproduce Prokerala exactly. Their tara table needs reading carefully: each
window carries the name of one tara but lists fifteen nakshatras, which is five
taras worth - the list is every janma star the window *favours*, not the three
holding the named tara.

### Nakshatra reference data
Deity, ganam, symbol, animal sign, nadi, colour, best direction, syllables,
birth stone, gender, ruling planet and enemy yoni, for all twenty-seven.

### Numerology
Thirty-six numbers, Pythagorean and Chaldean.

### Places
628,887 settlements resolved offline from GeoNames, with IANA timezone history
(including India's wartime +06:30).

---

## Endpoints

| Endpoint | Returns |
|---|---|
| `POST /v1/chart` | the whole chart; optional blocks behind `include_*` flags |
| `POST /v1/chart/summary` | a token-cheap text rendering for an LLM prompt |
| `POST /v1/yogas` | yoga detection with the evidence behind each verdict |
| `POST /v1/transits` | gochara only |
| `POST /v1/ashtakavarga` | bindu tables only |
| `POST /v1/upagrahas` | the eleven upagrahas |
| `POST /v1/doshas` | Kaal Sarpa, papasamyam, Mangal dosha |
| `POST /v1/relationships` | the three friendship tables |
| `POST /v1/sudarshana` | the chart from Lagna, Sun and Moon; ayana and ritu |
| `POST /v1/bala` | tara bala, chandra bala, chandrashtama for a date |
| `POST /v1/muhurta` | a calendar date's periods at a place |
| `POST /v1/matching` | Ashtakoot, from two births |
| `POST /v1/porutham` | the Tamil checklist, from two nakshatras |
| `POST /v1/kp` | cusps, sub lords, significators |
| `POST /v1/nakshatra` | the janma nakshatra with its full reference block |
| `POST /v1/numerology` | the thirty-six numbers |
| `GET /v1/places` | offline place search |
| `GET /v1/timezone` | IANA zone and offset for coordinates |
| `GET /v1/tool-definition` | JSON schema for wiring the chart up as an LLM tool |
| `GET /v1/tool-definitions` | all four tool schemas: chart, matching, muhurta, KP |
| `GET /health` | version, ephemeris backend, available ayanamsas |

---

## Where each rule comes from

Every block that carries a rule is stamped with a `source` and an `authority`
string. This is a different question from `parity`, and the two are
deliberately kept apart: a table can reproduce Prokerala on all 144 cells and
still have no textual authority behind it, which is exactly the case for most
of the porutham grid. From the numbers alone an LLM cannot tell the two apart,
so it is told.

| `source` | meaning | examples |
|---|---|---|
| `bphs` | traceable to Brihat Parashara Hora Shastra; the shloka is in `authority` | graha drishti, rashi drishti, contextual benefic/malefic, nakshatra deities, the sixteen vargas, the ashtakavarga bindu tables |
| `classical` | standard Jyotisha or a named system, but not BPHS | KP, tara/chandra bala, sun-derived upagrahas, numerology, the yoga set, gochara |
| `provider_compatible` | reproduces Prokerala and was recovered by measuring it; no textual authority | porutham, ashtakoot, muhurta, gowri, Kaal Sarpa, papasamyam, time-derived upagrahas, the non-deity nakshatra metadata, the ekadhipatya reduction |
| `unverified` | neither reproduced nor textually grounded | Daridra Yoga |

`GET /health` returns the vocabulary with its definitions, so a consumer can
learn all four in one call.

Three stamps are worth reading in full:

**Kaal Sarpa** is `provider_compatible`, not BPHS. BPHS describes *Sarpa
Yoga* — malefics in kendras — which is a different construct. The modern
all-grahas-between-the-nodes rule is not in it.

**The time-derived upagrahas** are mixed. The eight-part division of day and
night, Gulika at the start of Saturn's portion, and Mandi being the same
upagraha as Gulika are BPHS Chapter 3, verses 66-70. The part index itself,
`(lord index - vara) mod 8`, is not: it was recovered by inversion. The stamp
is `provider_compatible` because the indexing is what decides the answer.

**Ashtakavarga** splits the same way as the upagrahas. The bindu contribution
tables are BPHS Chapter 66 and the block is stamped `bphs`, but each
`ekaadhipatya` view carries its own `provider_compatible` stamp: the text is
ambiguous on the one clause that decides the table — an empty sign holding
strictly less than its occupied twin is zeroed, while an exact tie is left
alone — and that reading was measured, not read.

**Gochara** is `classical`, not BPHS. The ingress dates are computed by
bisecting the ephemeris, but the phase labels and the `description` prose
reproduce Prokerala's own strings so the two can be compared directly. That
prose is theirs, not doctrine.

**The nakshatra reference block** carries two stamps. `deity` is BPHS Chapter
3; the other eleven fields were transcribed from Prokerala and are stamped
`provider_compatible`, with the BPHS deity provenance in a nested
`nakshatra_deity_source`.

---

## Parity

Run everything:

```bash
python validation/verify_everything.py
```

```
suite                                status  summary
unit tests                           ok      258 passed
planetary positions vs NASA JPL      ok      28 comparisons, worst deviation +0.135 arcsec
sunrise, ayanamsa vs published       ok      All external checks passed
full Prokerala sweep                 ok      508/508 checks pass
numerology vs spec                   ok      36 matched, 0 differ
yogas                                known   20 of 21 yogas agree on every chart
ashtakavarga                         ok      204/204 checks pass
muhurta                              known   887/888 checks pass
papasamyam points                    ok      weights exact over 36 charts
tara and chandra bala                ok      24/24 checks pass
matching                             ok      418/418 checks pass
porutham                             ok      648/648 checks pass (all twelve rules)

12/12 suites clean
```

Responses are cached under `validation/.cache`, so re-runs are free and take
about a minute. Deleting the cache means refetching, which spends real credits.

The bundled `ephe/` directory is found automatically; `SE_EPHE_PATH` still
overrides it. Only if neither holds `.se1` files does Swiss Ephemeris fall
back to Moshier, which is accurate to about an arcsecond rather than a
milliarcsecond -- enough to pass every ordinary check and then fail the
tightest parity sweeps for no visible reason.

Sweeps fetch through `validation/parallel_fetch.py`, which gives each
configured Prokerala app its own worker, token and rate budget. The free tier
allows five requests a minute *per app*, so nine apps turn a forty-minute
sweep into four.

### Three conventions found by reverse engineering

**Reference equinox.** Prokerala subtracts the *nutation-free* ayanamsa from the
apparent tropical longitude; Swiss Ephemeris's `FLG_SIDEREAL` subtracts the
nutation-included one. The difference is the nutation in longitude — ±17
arcseconds on an 18.6-year cycle, so it is not a constant you can calibrate
away. Matching their convention took the residual to 0.00″ on four epochs.

**Julian year.** Dashas advance on 365.25 days, not the Gregorian 365.2425.
Found from an exact −7.50 milli-day-per-year drift.

**Part counting mod 8.** The upagrahas divide the day into eight parts but there
are only seven weekday lords, so the obvious reading — "the portion of Saturn",
counted mod 7 — agrees for some weekdays and is off by one for the rest. The
rule is `(lord index − vara) mod 8`. This was not read from a text: Prokerala's
longitudes for six weekday and day/night combinations were inverted back into
the moment the Lagna held them, and all thirty-six measurements landed on an
exact eighth or half-eighth.

### Tables that the textbooks get wrong for Prokerala

| Table | Correction |
|---|---|
| Ashtakavarga ekadhipatya | an empty sign holding *less* than its occupied twin is zeroed, but on an exact tie it is left alone |
| Vasya koot | three of the twenty-five cells |
| Gana koot | two of the nine cells |
| Yoni koot | Buffalo–Elephant are friends, Lion–Deer are enemies |
| Stree Deergha | starts at count nine, not thirteen |
| Yoni porutham | fails only on permanent enmity |
| Veda porutham | Chitra joins the Mrigashirsha–Dhanishta pair, making a triple |
| Choghadiya | the night list runs *backwards* through the cycle, two places per slot |
| Kaal Sarpa | their spellings: Vaasuki, Padam, Mahapadam, Shankhchurn, Paatak, Vishakt, Sheshnaag |
| Gana porutham | its own three-cell table, not the gana koot behind a threshold - a Rakshasa groom with a Manushya bride passes here and scores zero there |
| Rajju porutham | not the five body bands. Only every third star can clash at all, in two bands: `{1,7,13,19,25}` and `{4,10,16,22}`. The other eighteen pass even against themselves |
| Nadi porutham | not a partition. Mula belongs to no band, so it clashes with nobody; Purva Ashadha belongs to two, so it clashes with two thirds of the zodiac |
| Papasamyam points | one point from the Lagna, half from the Moon, a quarter from Venus, regardless of which malefic carries the dosha |
| Rasi porutham | not count-based at all; the classical "reject the 2nd and the 12th" gets 100 of 144 sign pairs |
| Rasi Lord porutham | rejects exactly three lord pairs - Sun/Saturn, Sun/Venus, Moon/Mercury - where the classical enemy rule rejects many more and gets 104 of 144 |
| Vashya porutham | a different table from the ashtakoot vasya groups, which get 42 of 144 |

### Known disagreements

Two, both measured and neither papered over.

**Daridra Yoga** is marked `"parity": "unverified"`, and the search behind
that is worth stating because the negative result is solid rather than a
shrug. Fifteen charts left twenty-seven one- and two-term formulas fitting
perfectly -- the signature of too little signal, not of success. Twenty-four
further charts were then chosen specifically where those twenty-seven
disagreed most sharply, each splitting the field about in half, and fetched.
All twenty-seven died.

On the resulting thirty-nine charts an exhaustive bitmask search over 378
predicates finds **no formula in one, two or three terms**. With 39
independent verdicts a candidate fits by luck with probability `2**-39`, so
the expected number of spurious fits across the entire search is about `1e-5`.
If a three-term rule existed it would have shown. Prokerala's Daridra must
therefore be a longer formula, or use something this engine does not model --
shadbala, a divisional chart, or an aspect scheme.

**Two charts out of eighteen** get Kaal Amrita from Prokerala for a
configuration that is unambiguously Kaal Sarpa and that they label Kaal Sarpa in
other years. Mean nodes fit better than true, retrogression does not explain it,
and no house-based reading separates it. Left disagreeing rather than
special-cased.

Two further items are Prokerala being internally inconsistent rather than this
engine being wrong: one Gowri Nalla Neram slot on Saturday night repeats a name
instead of closing its own rotation, and Brahma Muhurat is anchored about 23
seconds off an endpoint their own panchang reports differently.

### The off-by-one that hid four rules

Rasi, Rasi Lord, Vashya and Varna resisted everything for a long time. They
carry sign names, but on the sign this engine computes they are not sign
rules: hold the sign fixed, move the nakshatra underneath it, and the answer
changes. They also appeared to depend on the pada in a way no modulus
explained.

Both symptoms had one cause. **Prokerala counts the pada from one where it
should count from zero**, so the sign it uses for a nakshatra pada is one pada
further along than the real one. Chitra pada 1 and pada 2 are both Virgo;
Prokerala reads the second as Libra.

Corrected, all four become exact functions of the sign pair - all 144 cells,
no contradiction anywhere across 954 measured pada combinations. Varna is then
simply the ordinary varna rank, and Rasi Lord rejects three mutual-enemy lord
pairs. Rasi and Vashya are carried as measured 12x12 tables because their
classical forms fit only 100 and 42 of 144 cells.

The engine reproduces their sign, because it is observable and consistent.

### A bug on their side worth knowing about

`thirumana-porutham` takes a pada from 1 to 4. **Pada 4 is broken.** Sending
`girl_nakshatra_pada=4` or `boy_nakshatra_pada=4` makes every star-based check
behave as though that person were in the first pada of the *next* nakshatra -
and for Revati it wraps round to Ashwini. Pada 0 is rejected outright, so this
is not an undocumented zero-based convention; it is an off-by-one.

The rasi-based checks are unaffected, because the fourth pada of one star and
the first of the next cover the same three degrees twenty of the zodiac.

The engine does not imitate this. Validation sweeps avoid pada 4 instead. It
cost most of a day to find: an early sign sweep used all four padas, and the
resulting "failures" in five already-verified rules were entirely this bug.

### Not checked at all

**The Western endpoints** - natal aspect grids, transit, progression, solar
return, synastry and composite charts - are deliberately out of scope. They are
a tropical system with a different house and aspect model, they cost 500 to 800
credits each, and none of them is part of a kundli.

### Precision notes

- Planetary longitudes agree with NASA JPL to **0.135 arcsec** worst case.
- Sunrise and sunset agree with Prokerala's panchang to **about a second**, but
  the sunset and next-sunrise they feed the muhurta endpoints scatter by up to
  seven — a lower-precision solar routine on their side. Slice boundaries
  inherit that, so muhurta timings can differ by up to twelve seconds.
- Upagraha longitudes agree to **68 arcsec** worst case across 88 placements,
  from the same cause.

---

## Install

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

Optionally fetch the Swiss Ephemeris data files for full 0.001″ precision —
without them the engine falls back to Moshier, which stays under 0.1″ and needs
no files at all:

```bash
set SE_EPHE_PATH=%CD%\ephe
```

Build the offline place index once (about a minute):

```bash
python -m astro_engine.places build
```

---

## Layout

```
astro_engine/
  ephemeris.py     Swiss Ephemeris wrapper. Every number originates here.
  chart.py         assembles one complete birth chart
  constants.py     static Jyotisha reference data, no computation
  vargas.py        the sixteen divisional charts
  dasha.py         Vimshottari
  panchanga.py     tithi, nakshatra, yoga, karana, vara
  transits.py      gochara, Sade Sati, returns
  ashtakavarga.py  bindu tables and both reductions
  upagraha.py      the eleven sub-planets
  relationships.py naisargika, tatkalika, panchadha maitri
  doshas.py        Kaal Sarpa, papasamyam
  muhurta.py       choghadiya, hora, kaal periods, gowri, disha shool
  matching.py      Ashtakoot guna milan
  porutham.py      the Tamil checklist
  kp.py            Krishnamurti Paddhati
  yogas.py         twenty-four yogas
  numerology.py    Pythagorean and Chaldean
  places.py        offline GeoNames geocoder
  geo.py           local time to UTC, with full timezone history
  calendar_points.py ayana, ritu, Sudarshana Chakra
  bala.py          tara bala, chandra bala, chandrashtama
  provenance.py    where each rule comes from: bphs / classical /
                   provider_compatible / unverified
  provider.py      durable record wrapper, for storing charts
  api.py           FastAPI surface

validation/        parity scripts; verify_everything.py runs them all
tests/             291 tests
deploy/            serve script and Cloudflare Tunnel config
```

---

## Licence

Swiss Ephemeris is AGPL-3.0. That is fine for personal use and for open source.
A closed-source network service needs the commercial licence from Astrodienst.
