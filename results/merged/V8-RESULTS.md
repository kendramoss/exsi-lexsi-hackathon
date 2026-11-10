# EvidenceTune v8 — targeted + two-turn continuation — 9 Nov 2026

**Verdict: v8 is NOT a replacement for v7 on the main correction benchmark. Dev selection chose baseline_v7. A small two-turn pilot nevertheless shows a promising resolution improvement that needs a larger independent evaluation.**

## Main correction benchmark

| Metric | v7 baseline | v8 targeted + two-turn |
|---|---:|---:|
| Dev row task success | **87.78%** | 86.67% |
| Frozen row task success | **92.96%** | 86.67% |
| Frozen all-five-condition case success | **77.78%** | 48.15% |
| Frozen action correctness | **93.06%** | 83.80% |

- Selection used new-v8 dev only, not frozen test or resolution dev.
- Original-v6 semantic-dev retention passed within tolerance: task success −4.17pp and action correctness −4.69pp, both within the allowed 5pp drop.
- Frozen evaluation used the reviewed 54-case independent targeted pack.

## Two-turn resolution pilot (only 4 cases / 16 initial rows)

| Metric | v7 baseline | v8 |
|---|---:|---:|
| Overall clarification resolution | 70.0% | **83.3%** |
| Final dialogue task accuracy | 90.6% | **96.9%** |
| Fully resolved cases | 25.0% | **75.0%** |
| Clarification calls per resolved case | 1.43 | **1.20** |
| Total model calls | 26 | **22** |

The pilot suggests better resolution and fewer calls, but the sample is too small for a superiority claim. It was not used for model selection.

## Interpretation

- Keep **v7 as the current general correction model**.
- Treat v8's single-turn/frozen regression as real within this experiment.
- The next useful step, if pursued, is a **larger resolution-only evaluation** of v7 vs v8 on non-fresh cases. Do not retrain or tune on this frozen test to rescue v8.
- Results are Kaggle fp16, contract-v2 synthetic/proxy evaluations; they do not establish broad natural-domain or human-validated generalization.

Artifacts: `results/v8/evtune-v8-output/` after Kaggle output download. Selection, retention, raw AuditKIT and native-resolution records are included.
