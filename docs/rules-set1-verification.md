# Rule set 1 verification: house lords in houses

Rules: `astro_rules/rules/house_lords.yaml`, 144 rules (12 lords x 12 houses).

Sources:
- Primary: BPHS, G.C. Sharma translation, Vol.1, **Chapter 26** "Effects of
  the Bhava Lords", verses 1-144 (PDF pages 283-346, read as images).
- Cross-check: BPHS, R. Santhanam translation, Vol.1, **Chapter 24** (same
  title). The editions number the chapter differently; the verses match one
  for one. `docs/PLAN-interpretation.md` calls it Ch.24 (Santhanam numbering).

## Pass 1 (transcription)

Each verse read in Sharma, then compared with Santhanam. Santhanam's OCR text
is damaged for v7, 11, 12, 27-30, 69-72, 132-136; for those, legible fragments
were compared and the rule carries a `note`.

Variants recorded in pass 1: v8 (occult knowledge vs scholar), v26
(unhappy vs happy, OCR doubt), v32 (killed by king vs dies at palace gate),
v41 (favourite of all vs like a bull), v95 (8th lord in 11th: unconditional vs
"with a malefic"), v142 (rises vs spends through royal persons).

## Pass 2 (independent re-read)

A separate reader re-read every verse in both books without the pass-1 notes
in view. Result: 138 agree, 6 disagree. All six were re-checked against the
Sharma page images and accepted:

| Verse | Rule | Disagreement | Resolution |
|---|---|---|---|
| 12 | 1_in_12 | Only the spending and anger depend on "no benefic"; lack of bodily comfort is unconditional. | Base meaning narrowed; clause now `not associated_with benefic` -> wasteful spending, anger. |
| 14 | 2_in_2 | "May be without children" softened the verse. | Now "without children". |
| 16 | 2_in_4 | Sharma: Jupiter OR exalted; Santhanam: exalted AND Jupiter. | Both clauses encoded; flagged with variants. |
| 42 | 4_in_6 | "Magician" is Santhanam only; Sharma: man of questionable character. | Flagged with variants. |
| 53 | 5_in_5 | Sharma needs benefic conjunction and ties "virtuous, dear to friends" to the malefic case. | Flagged with variants. |
| 143 | 12_in_11 | "Brought up by others" is Santhanam only. | Meaning based on Sharma; flagged with variants. |

Minor wording differences judged not material (kept, some noted): v24, v55,
v61, v69, v88, v102.

After resolution both passes agree on all 144 rules.

## Flagged rules (10)

1_in_8, 2_in_4, 3_in_2, 3_in_8, 4_in_5, 4_in_6, 5_in_5, 8_in_11, 12_in_10,
12_in_11. Each carries both readings in `variants`; `/v1/rules` returns them.

## Not evaluated

- 8_in_8: the "weak lord -> medium life" branch needs strength (shadbala).
- Verses 145-148 (dual lordship, strength scaling) are guidance for the
  weighting phase, not rules.
