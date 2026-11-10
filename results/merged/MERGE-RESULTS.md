# EvidenceTune v7/v8 interpolation — 9 Nov 2026

**Result: `merge_alpha_0.75` (75% v7 + 25% v8) is the new best candidate. It improves both single-turn and resolution behavior on dev and confirms on frozen tests.**

Adapter: `merge_eval/adapters/alpha_0.75`
SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`

## Dev selection

| Metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 94.58% | **96.25%** | +1.67pp |
| Targeted task success | 87.22% | **90.00%** | +2.78pp |
| Conditional resolution | 38/50 (76.00%) | **27/34 (79.41%)** | +3.41pp |
| Final dialogue task accuracy | 81.25% | **83.20%** | +1.95pp |

Only v7 and α=0.75 passed the preregistered retention/resolution gates. Selection used dev only. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.** Resolution is conditional on different CLARIFY follow-up denominators (50 versus 34), not same-denominator paired outcomes.

## Frozen confirmation

| Metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic frozen task success | 88.75% | **92.50%** | +3.75pp |
| Targeted frozen task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

All **1,020 frozen predictions** and metrics were independently verified. **17 tests pass.**

## Scope

- Apple MPS bf16 local inference; not directly comparable with historical Kaggle fp16/RTX runs.
- AuditKIT produced source-model evaluations. Merged interpolation and current MPS dev/frozen and native-resolution results used custom EvidenceTune contract-v2/native scorers. Raw base Tiny Aya was not evaluated on current contract-v2 suites, so base→merged correction improvement is unmeasured.
- Selection: `merge_eval/local_results/evaluation/selection.json` SHA-256 `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b`.
- Frozen summary: `merge_eval/local_results/frozen_confirmation/frozen_summary.json` SHA-256 `3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d`.
- These remain contract-v2 synthetic/proxy evaluations, not independent human or broad natural-domain validation. The larger resolution evaluation has 32 non-fresh cases; the original 4-case v8 pilot was not used for selection.
- No training, Kaggle job, or publication occurred.
