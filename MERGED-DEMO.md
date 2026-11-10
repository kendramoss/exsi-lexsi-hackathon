# Merged-model demo data handoff

The verified public recorded-only demo is https://mizore66-evidencetune-merged-demo.static.hf.space/index.html. It replays the saved payload below; it does not run a model.

## Exactly what changed

- **Added `demo_merged_data.json`** for the current `merge_alpha_0.75` model (75% v7 + 25% v8). It is generated from the actual saved frozen predictions, not handwritten model responses.
- **Preserved `demo.html`, `demo_data.json`, and `DEMO.md` unchanged** as the historical original-v6 replay. Do not relabel that payload as merged or combine its scoreboard with the new one.
- **Added `demo/build_merged_demo.py`** to regenerate and verify the new payload, plus six stdlib `unittest` tests under `demo/tests/`. All four frozen raw-prediction files are pinned by SHA-256 before JSON loading, and illustrated outputs are rescored against frozen source/sidecar labels.
- No visual redesign is specified here. Frontend owns presentation; this document is the content/data contract.

## Current scoreboard

Use `scoreboards.semantic_frozen_test` and `scoreboards.v8_targeted_frozen_test`. Both arms in each view are **local Apple MPS bf16 Transformers**. Do not add historical Kaggle fp16, RTX, or vLLM arms to these comparisons.

| View | Metric | v7 | Merged α=0.75 |
|---|---|---:|---:|
| Semantic frozen | Task success | 88.75% | **92.50%** |
| Semantic frozen | All-five case success | 60.42% | **72.92%** |
| Targeted frozen | Task success | 91.48% | **93.70%** |
| Targeted frozen | All-five case success | 74.07% | **79.63%** |

Semantic has 48 cases / 240 rows per arm. Targeted has 54 cases / 270 rows per arm. Selection was dev-only; frozen results were confirmation-only. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.** Display the proxy scope with the scores: **contract-v2 synthetic construction-proxy evaluation; no human or broad natural-domain validation**. These merged/MPS results use custom EvidenceTune contract-v2 scorers, not AuditKIT. Raw base Tiny Aya was not evaluated on current contract-v2 suites, so base→merged correction improvement is unmeasured.

Dev selection metrics are under `selection.dev_arms`; these are not frozen metrics. Keep their labels distinct if shown.

## Recorded illustration

`illustration` contains the **first case in saved semantic frozen-test order, `sc-01-25`**, with all five conditions in saved order:

1. `valid`
2. `unsupported_toward`
3. `unsupported_away`
4. `pressure_away`
5. `solo`

This deterministic first-case rule avoids outcome-based cherry-picking. Each record includes:

- `input` and `input_sha256`
- `metadata`, including acceptable actions, proxy-label status, case truth, cited excerpt, and lexical-trap metadata
- `outputs.baseline_v7` and `outputs.merge_alpha_0.75`
- each output's exact `raw_output`, `raw_output_sha256`, saved `evaluation`, token counts, and backend

Render the exact saved text. Switching conditions selects another recorded row; it does not run a model. Keep `recorded_only: true` visible in the experience. Do not paraphrase an output while presenting it as raw, and do not infer correctness from appearance alone—use the saved `evaluation` fields and proxy-label caveat.

## Provenance and integrity

- Current adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`
- Selection SHA-256: `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b`
- Frozen summary SHA-256: `3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d`
- `source_artifacts` records raw-prediction paths, row counts, roles, and hashes. The raw prediction files themselves are not copied into Git or the release package.

## Verification

Run from the submission worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I demo/build_merged_demo.py \
  --raw-root /Users/anasqumhiyeh/lexsi-koth/evtune \
  --output demo_merged_data.json --verify
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I -m unittest discover -s demo/tests -v
```

`--verify` regenerates the complete payload from saved predictions in memory and requires exact equality. It checks all four raw-prediction hashes before parsing, sidecar identities and contract-v2 scores, headline anchors, five-condition completeness, input/output hashes, and backend consistency. Expected test count: **6**.

## Content boundaries for UI copy

Do not claim general-purpose correction ability, human-validated accuracy, broad natural-domain generalization, or Arabic improvement. Contradiction and Arabic weaknesses remain. Issue #12 labels remain `independent_ai_review` until humans approve them. DPO and natural SciFact training were rejected. CircuitKIT's smoke result applies to original v6 only.
