# Plan: from exact facts to accurate readings

Status: draft, not started. Engine at 1.2.2 live; 1.3.0 (strict_bphs + cleanup,
`bea5eac`, `c09cbcf`) is committed locally and not pushed.

## Goal

Answers that are correct by the tradition, explain their reasoning and cite
their source. Make the LLM interpret facts the engine computed and rules a
book states, and never invent either.

```
Birth data
  -> Engine        exact facts (positions, dignity, yogas, dashas)      DONE
  -> Strength      shadbala + bhava bala: how strong is each planet     Phase 1
  -> Rule layer    what the books say each placement means              Phase 2
  -> Case memory   real charts with known life events                   Phase 3
  -> Weighting     which fired rules matter in this chart, now          Phase 4
  -> LLM layer     writes the reading from the above, with citations    Phase 5
```

Each phase ships on its own and is useful without the next one.

## Principles

- **Engine stays pure calculation.** Interpretation lives in a separate
  package (`astro_rules/`) so the engine's parity and audits are untouched.
- **Every rule carries a citation**: book, chapter and verse, plus the
  provenance tag (`bphs` / `classical` / `provider_compatible` /
  `unverified`). A rule with no citation does not ship.
- **Measure, don't assert.** Accuracy claims come from the case bench
  (Phase 3), never from the rules agreeing with themselves.
- **Same gates as today.** Before each commit: full pytest,
  `against_bphs.py` and `verify_everything.py` must pass. No push without
  the user's go-ahead (a push to main deploys to production).
- **Books stay out of git** (`docs/bphs/`, `docs/books/`, gitignored).
  Only short citations go into code.

## Phase 1: Shadbala and bhava bala (engine)

Why: weighting is impossible without a planet-strength number. It is the
largest piece of BPHS the engine does not compute.

Scope (BPHS Ch.27-28; Raman, *Graha and Bhava Balas*):
- Sthana bala: uchcha, saptavargaja, ojayugma, kendra, drekkana.
- Dig bala.
- Kala bala: nathonnata, paksha, tribhaga, abda/masa/vara/hora, ayana,
  yuddha.
- Chesta bala (from true speed, mean motion and the chesta kendra).
- Naisargika bala.
- Drik bala.
- Totals in virupas and rupas; ishta/kashta phala; the minimum-required
  ratio.
- Bhava bala: bhavadhipati, bhava dig, bhava drishti.

Deliverables:
- `astro_engine/shadbala.py`, plus `include_shadbala` on `/v1/chart`.
- Provenance blocks per component.
- Tests: each component on Raman's worked example charts, to his printed
  virupas (tolerance about 0.1 virupa where his tables round).
- `against_bphs.py` checks citing Ch.27-28.
- If credits allow, a Prokerala/VedIntel comparison (both expose shadbala).

Needs: Raman's *Graha and Bhava Balas* (worked examples).
Risk: editions differ on yuddha bala and the chesta details. Pick
Raman/BPHS, document the choice, and keep a provider-compatible variant only
if the measured difference is large.
Size: large. About 1-2 worker sessions.

## Phase 2: Rule layer (new package `astro_rules/`)

Why: stops the LLM inventing meanings. It looks rules up instead.

Rule format (YAML, one file per area, loaded and validated at import):

```yaml
- id: bphs.house_lords.9_in_10
  when: { lord_of: 9, in_house: 10 }
  meaning: "Fortune through career; authority and recognition."
  polarity: positive          # positive | negative | mixed
  domains: [career, fortune]
  source: { book: BPHS, edition: Sharma, ch: 24, v: "..." }
  provenance: bphs
```

- A small condition language: lord_of, in_house, in_sign, dignity,
  conjunct, aspected_by, yoga_present, dasha_lord.
- It evaluates against the engine's existing JSON, with no new astrology
  maths.
- `POST /v1/rules`: chart in, fired rules out, each with its evidence (which
  facts made it fire).

Order of rule sets, highest value first:
1. House lords in houses (BPHS Ch.24): 144 rules.
2. Planets in houses (BPHS Ch.25-26 + Phaladeepika): 108.
3. Planets in signs + dignity: 84.
4. Yoga results (yogas the engine already detects).
5. Dasha and antardasha results (BPHS Ch.47-62).

Verification: astroVerify transcribes each set from the book, then a second,
independent pass re-reads the verse for every rule, as was done for the
207 checks. The two passes must agree.

Needs: BPHS (have it); Phaladeepika for set 2.
Size: medium per set. Set 1 is a good first slice.

## Phase 3: Case memory (test bench)

Why: the only honest way to measure accuracy.

- `validation/cases/*.yaml`: birth data, source/page, and dated life events
  (marriage, career change, children, illness, death) with categories.
- 50-100 charts from Raman's *Notable Horoscopes*, then K.N. Rao's books.
- Rodden rating recorded for every birth time. Only AA/A ratings count
  toward accuracy scores.
- `validation/case_bench.py`: for each event, which dasha/antardasha was
  running, and which fired rules point at that domain. Output: hit rates per
  domain, compared against a random-timing baseline.

Needs: *Notable Horoscopes*; later K.N. Rao.
Risk: published charts are selected to fit the author's point (survivor
bias). Report results against the random baseline, never as raw hit rates.

## Phase 4: Weighting

Why: a chart fires 50+ rules, many of them contradictory. Weighting decides
what to say first.

Score per fired rule = f(shadbala of the planets involved, dignity, whether
the planets' dasha/antardasha is running, yoga cancellations, aspects).

- Start with a transparent hand-written formula taken from the texts
  (strong vs weak, BPHS ishta/kashta).
- Tune its few weights on the Phase 3 bench. Hold out 30% of cases.
- Output: ranked rules, plus "active now" vs "latent".

Rule: the weights must stay explainable (a handful of numbers, not a black
box), so every reading can say why one rule outranked another.

## Phase 5: LLM layer

- Input: engine facts + ranked fired rules + 2-3 similar cases from case
  memory.
- The prompt forbids stating any placement or meaning that is not in the
  input, and requires a citation per claim.
- Eval: replay bench charts and check that the claims trace back to input
  rules (faithfulness), plus spot review by a practising astrologer if
  available.

## Out of scope for now

- Jaimini / chara dasha, Yogini, Ashtottari (later engine phase).
- Tajika / varshaphal, prashna.
- Settling the Kemadruma and nodes-in-Sunapha readings (needs Santhanam's
  BPHS; small, can run alongside any phase).

## Books, in the order they are needed

1. Raman, *Graha and Bhava Balas* (Phase 1)
2. Raman, *Notable Horoscopes* (Phase 3)
3. Santhanam's BPHS (second translation; tie-breaks)
4. Phaladeepika (Phase 2, set 2)
5. K.N. Rao's timing books (Phase 3 expansion)

Grab both PDF and FULL TEXT. Check text quality before starting a phase
(the Sharma BPHS PDFs had unreadable built-in text).

## Immediate next steps

1. Push 1.3.0 (strict_bphs + cleanup), once the user approves.
2. User downloads books 1 and 2.
3. Phase 1 (shadbala) goes to the worker, with the same gates.
