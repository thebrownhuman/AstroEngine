# Shadbala: conventions and Raman errata

Phase 1 of `docs/PLAN-interpretation.md`. Code: `astro_engine/shadbala.py`.
Tests: `tests/test_shadbala.py` (Raman's Standard Horoscope, 0.1 virupa).
Checks: `validation/against_bphs.py` 90-101 (BPHS Ch.27).

API: `POST /v1/shadbala` (ChartRequest body) and `include_shadbala: true` on
`/v1/chart` (default false, so the default response is unchanged). The old
`/v1/bala` is the daily tara/chandra bala and is untouched: it takes a day,
not a birth, so a separate endpoint is clearer than a sub-key.

## Sources

- B. V. Raman, *Graha and Bhava Balas* ("Raman"). He follows Sripati and
  works every component on one chart; that chart is the test fixture.
- BPHS Ch.27-28, Santhanam translation ("BPHS"). Verse numbers below are
  Santhanam's section numbers.

The default `convention="raman"` reproduces Raman. `convention="bphs"`
switches the four points marked **(switch)**. The API serves the default.

## Choices between conflicting conventions

| Point | Raman (default) | BPHS / others | Why |
|---|---|---|---|
| Saptavargaja grade values **(switch)** | 45/30/22.5/15/7.5/3.75/1.875 (Art. 30) | Santhanam 27.2-4: 45/30/20/15/10/4/2 | Raman's halving series reproduces every one of his Example 9 totals. |
| Moolatrikona | Rasi only, 45 | Same | Degree spans from `constants.MOOLATRIKONA` (BPHS 3.49-54). |
| Drekkana bala **(switch)** | male 1st, hermaphrodite 2nd, female 3rd, 15 each (Art. 36, Ex. 12) | Santhanam's notes to 27.6: female 2nd, eunuch 3rd | Raman's worked example uses his order. His Ch. XI summary says "60" but every worked figure is 15; we use 15. |
| Kendra bala | by sign from the Lagna (Art. 33, Parashara's view) | Sripati's commentator: by bhava | Raman explicitly sides with Parashara. |
| Dig bala reference points | Sripati bhava madhyas: Lagna, IC (MC+180), descendant, MC | BPHS "cusps" | Same as the true angles for Sripati houses. |
| Nathonnata | Method B from local apparent time (Art. 51) | BPHS 27.8-9 in ghatis of nata | Equivalent; LAT = LMT + equation of time (Swiss Ephemeris). |
| Paksha | benefics get elongation/3, malefics 60 less; Moon always the benefic value, doubled | Same | Moon "benefic" = waxing (elongation 0-180) for drik bala. Raman Art. 53 also mentions an 8th-tithi boundary; not used. |
| Mercury's nature | malefic when in the same sign as the Sun, Mars or Saturn (Raman Ex. 55 footnote) | BPHS 3.11 | Same rule as `chart._bphs_nature`, minus the nodes (they cast no drishti here). For bhava drishti Mercury is always benefic (Raman's footnote to Ex. 59). |
| Abda/masa/vara | Raman's condensed ahargana: (Vedic date - 1900-01-01) + 26,543, remainders counted from Wednesday (Arts. 60-64) | Surya Siddhanta ahargana from creation | Identical lords; the Vedic (sunrise) date is used so a pre-dawn birth gets the previous day's lords. |
| Hora | equal 60-minute horas from sunrise (Art. 70, Rule 1) | Many programs use day/12 and night/12 | Raman's rule. |
| Ayana bala | (24 +/- kranti)/48 x 60, Sun doubled; kranti from the sayana longitude by the 24-degree tabular sine (362/341/299/236/150/52', Art. 73) | BPHS 27.15-17 gives khandas 45/33/12; modern code uses true declination | Reproduces Raman; ecliptic latitude ignored as he does. Ayanamsa: the chart's own. |
| Yuddha **(switch)** | Mars-Saturn within 1 degree; lesser longitude wins; (sthana + dig + kala up to hora) difference / disc-diameter difference (Arts. 76-77) | BPHS 27.20: plain difference of shadbalas | Raman. Several simultaneous wars use pre-war totals for every pair. |
| Chesta, Mars-Saturn | seeghrochcha - (mean + true)/2, folded, /3 (Sripati, Art. 105) | Same; BPHS 27.21-23 also lists 8 motion states | Mean longitudes and seeghrochchas from Raman's epoch constants and daily rates (Arts. 94-103, Kedarnath Dutt's tables) with his secular corrections. Rates read off his 6,000-day rows. |
| Chesta, Sun and Moon **(switch)** | excluded from the shadbala total (Ex. 56); computed separately for ishta/kashta (Ch. X: Sun = (sayana+90) folded /3, Moon = elongation/3) | BPHS 27.18: Sun's = ayana bala, Moon's = paksha bala, counted in the total | Raman's totals. Under `bphs` the luminaries' chesta enters the total. |
| Ishta/kashta | sqrt(uchcha x chesta), sqrt((60-uchcha)(60-chesta)) (Ch. X) | BPHS 28.6 via rasmis | Raman. |
| Bhava drishti | quarter of each planet's drishti (special aspects added first), whole of Jupiter's and Mercury's | Same | Raman Art. 132. |
| Bhava dig | 10 virupas per bhava from the class's zero point: Keeta 1, Chatushpada 4, Nara 7, Jalachara 10 (Art. 131) | Same | |

### Known limitation

Raman's mean longitudes are referred to his own sidereal frame. The engine
feeds them the chart's true longitudes (Lahiri by default). A frame offset of
about 1 degree shifts a chesta kendra by about 0.5 degree, i.e. 0.15 virupa.
Not corrected; a modern mean-element variant can be added if a provider
comparison shows a larger difference.

## Where Raman's printed numbers are wrong

Each was recomputed from his own inputs; the test asserts the recomputed value.

| Where | Printed | Correct | Cause |
|---|---|---|---|
| Ex. 3, Mars uchcha | 37.06 | 37.17 | 111 30' 34" / 3 |
| Ex. 33, Mars ayana | 1.84 | 1.96 | kranti 22.43 (he writes 22.45) |
| Ex. 32-33, Jupiter ayana | 59.40 | 58.86 | kranti 1385' = 23 05' read as 23.5 degrees |
| Ex. 32-33, Saturn ayana | 13.75 | 13.55 | kranti 790' = 13.16 used as 13.0 |
| Ex. 35, Mars kala total | 33.06 / 30.06 | 30.17 | the two errata above |
| Ex. 56, Sun total | 424.24 | 424.94 | addition; his rupas (7.08) are right |
| Ex. 56, Mercury rupas | 8.85 | 8.95 | 537.02 / 60 (also carried into Ex. 57-58) |
| Ex. 56, Saturn naisargika | 8.37 | 8.57 | typo; total uses 8.57 |
| Ex. 63, Mercury kashta | 49.16 | 17.8 | uses 60 - 1.30 for 60 - 2.30, and garbled |
| Ex. 59, Bhava I, Saturn's drishti | 13.00 | 12.03 | his subtotal 25.81 implies 12.03 |
| Ex. 59, Bhava XII total | 426.76 | 526.76 | 389.21 + 40 + 97.55 |
| Ex. 50, reduced kendras | -- | -- | column misaligned in the scan; Ex. 51 values used |

Knock-on: Mars, Jupiter and Saturn totals (and bhavas they lord) differ from
his by 0.1-0.5 virupa because of the uchcha/ayana errata. Every other cell
matches within 0.1 (bhava drishti within 0.25, his per-cell rounding).

Components that do not match Raman after correction: none.
