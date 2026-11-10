# EvidenceTune v7 — semantic-contrast training — 8 Nov 2026

**Result: v7 (`v6_semantic`) clearly outperforms the original v6 baseline on the new held-out-constructor evaluation. Dev selection chose v7, not the baseline. Raw AuditKIT evaluation is complete: 240/240 predictions per model per split, zero errors. The adapter download is being verified separately.**

## Comparison

| Metric | Original v6 | v7 semantic | Delta |
|---|---:|---:|---:|
| **Dev task success** | 73.75% | **95.00%** | +21.25pp |
| **Frozen-test task success** | 69.17% | **89.58%** | +20.42pp |
| Frozen-test lexical-trap task success | 50.00% | **81.67%** | +31.67pp |
| Frozen-test all-five-condition case success | 35.42% | **64.58%** | +29.17pp |
| Frozen-test action correctness | 69.79% | **90.62%** | +20.83pp |
| Frozen-test post-action answer correctness | 92.50% | **95.83%** | +3.33pp |

Each split has 48 independently constructed semantic cases / 240 matched rows. Dev ranking was fixed before frozen-test generation; `selection.json` selects `v6_semantic` and records `frozen_test_used_for_selection: false`.

## Recipe

- 3,115 freshness-filtered historical v6 rows + 720 reviewed semantic-contrast train rows = **3,835 rows**.
- The freshness registry removed 13 historical training-after-evaluation cases (65 rows) before curation.
- SafeTune PlainSFT, seed 0, two epochs, batch 1 with gradient accumulation 4, max length 1,024, single GPU, gradient checkpointing.
- CuratorKIT export and AuditKIT raw predictions/provenance retained.

## Interpretation limits

- **Kaggle fp16 Transformers**, not RTX bf16/vLLM-standardized results.
- **Contract v2 metrics**; do not compare these numbers directly with historical v1 headline percentages.
- **Synthetic construction-proxy labels**, not independent human sufficiency annotation.
- Frozen test supports only **narrow held-out-constructor generalization** in the synthetic three-excerpt setting, not broad natural-domain generalization.
- Five matched rows per case are correlated; the 240 rows are not 240 independent observations.
- The original baseline adapter is a historical artifact evaluated on the same new v2 prompts, so the paired comparison itself is meaningful even though its prompt format differs from its original v1 training data.

## Artifacts

`results/v7/evtune-next-output/`: baseline and tuned adapters, raw AuditKIT predictions, evaluation summaries, manifests and completion records. `results/v7/evtune-next-inputs/input_manifest.json` records input/freshness provenance. Adapter tensor completeness is **verified**: 120,981,200 bytes, exactly matching the declared tensor data and header.
