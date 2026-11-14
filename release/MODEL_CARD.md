---
base_model: CohereLabs/tiny-aya-global
library_name: peft
license: cc-by-nc-4.0
pipeline_tag: text-generation
tags:
  - lora
  - evidencetune
  - correction-routing
---

# EvidenceTune merged alpha=0.75

## Model summary

EvidenceTune merged alpha=0.75 is a LoRA adapter for `CohereLabs/tiny-aya-global`. It teaches a narrow correction contract: update when cited evidence settles the answer, retain under bare pressure, and clarify or retain when a citation is insufficient. It is an elementwise interpolation of two existing adapters: **75% v7 semantic-contrast + 25% v8 targeted/two-turn**.

This is the current EvidenceTune candidate for the Lexsi Track 2 submission. It is not a general-purpose chat model, not a human-validated system, and not evidence of broad natural-domain performance.

## Identity

- Adapter tensor file: `adapter/adapter_model.safetensors`
- SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`
- Size: 120,981,200 bytes; 504 tensors
- LoRA: rank 16, alpha 32, dropout 0.05, bias none
- Target modules: `up_proj`, `gate_proj`, `down_proj`, `v_proj`, `q_proj`, `o_proj`, `k_proj`
- Merge arithmetic: float64 interpolation, cast once to each source tensor dtype on CPU
- Source v7 adapter SHA-256: `736dcea313d0a4c54021b2b5a0af6d1dd5d1a0bf6d2c750a2a788e0a5d7dc1fd`
- Source v8 adapter SHA-256: `9985ca4829348a0eb7a32dfae37302921fe4af0485bc1fa114dd869dcc66e837`
- Adapter license: **CC BY-NC 4.0** (`LICENSE-MODEL`). Original project code is separately MIT licensed; dataset and Lexsi terms remain separate.
- Base-model attribution: **Tiny Aya Global, Cohere Labs**, https://huggingface.co/CohereLabs/tiny-aya-global. This adapter is not endorsed by Cohere Labs.

## Training and merge provenance

CuratorKIT produced validated packs, checksums, and provenance. SafeTune PlainSFT trained v7 from 3,115 freshness-filtered historical rows plus 720 reviewed semantic-contrast rows (3,835 total), seed 0, two epochs, LoRA rank 16, Kaggle fp16. V8 continued from v7 with targeted and two-turn data, seed 0, two epochs, Kaggle fp16. The merge itself performed no training and used no frozen cases.

The current selection compared v7, v8, and three interpolation weights on dev only. Only v7 and alpha=0.75 passed the preregistered semantic/targeted retention and resolution gates. Alpha=0.75 ranked first. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.** Frozen merged-model evidence was confirmation-only, not reselection.

## Intended use

Use for research on matched, three-excerpt correction routing under `evidencetune.task.v2`; inspect recorded predictions and compare against the same-backend v7 baseline. The expected output is `ACTION: UPDATE|CLARIFY|RETAIN` plus `ANSWER: ...` for correction rows, or an answer for solo rows.

## Out-of-scope use

Do not use as a factual arbiter, a general-purpose assistant, a safety-certified model, or a validated multilingual/natural-document correction system. Do not infer human agreement from synthetic construction labels or independent AI review.

## Evaluation

### Dev-only selection

| Metric | v7 | Merged alpha=0.75 |
|---|---:|---:|
| Semantic task success | 94.58% | **96.25%** |
| Targeted task success | 87.22% | **90.00%** |
| Conditional resolution | 38/50 (76.00%) | **27/34 (79.41%)** |
| Final dialogue task accuracy | 81.25% | **83.20%** |

The resolution expansion has 32 non-fresh cases. Resolution is conditional on CLARIFY episodes, so v7 and merged have different follow-up denominators (50 versus 34); the rates are not same-denominator paired outcomes. The earlier four-case v8 pilot was not used for selection. A post-selection raw-base arm was evaluated on the same suites/backend; it is descriptive only and did not affect model choice. See `BASE-EVALUATION.md` and `UNCERTAINTY.md`.

### Frozen confirmation, Apple MPS bf16

| Metric | v7 | Merged alpha=0.75 | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

Semantic: 48 cases / 240 rows per arm. Targeted: 54 cases / 270 rows per arm. All 1,020 raw records across the two arms were independently checked on 10 Nov 2026. Selection JSON SHA-256 is `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b`; frozen summary SHA-256 is `3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d`.

These Apple MPS bf16 figures must not be mixed with historical Kaggle fp16, RTX, or vLLM results. Five rows from one case are correlated, not five independent cases.

### Follow-up descriptive checks

On a separate 100-case authored synthetic evaluation, merged task success was 92.0% versus 89.2% for v7. Contradiction cases remained weaker than entailment cases: 87.2% versus 96.8% task success for the merged model. This is descriptive synthetic/proxy evidence, not independent human adjudication.

On the small reviewed Arabic proxy, both models scored 62/80 task successes; merged all-five success was 4/16 versus v7's 5/16, and merged solo accuracy was 4/16. Native-speaker adjudication is still required. This does not support an Arabic improvement claim.

On 750 safe XSTest-style prompts per model, the merged arm's automated over-refusal proxy was 54/750 (7.2%), compared with 56/750 (7.5%) for base and 53/750 (7.1%) for original v6. This is not a human refusal or answer-quality measure.

## Negative results and limitations

- **DPO rejected:** dev semantic task success fell from 96.25% to 94.58% and resolution from 79.41% to 78.57%; the unchanged merged baseline remained selected. No frozen generation was used.
- **Natural SciFact training rejected:** four reviewed generations retained fundamental scope and label ambiguity. Do not train or score against the pack; no generation 5.
- **Contradiction weakness remains:** merged synthetic contradiction performance trails entailment performance.
- **Arabic weakness remains:** small provisional proxy results are flat overall and worse on solo/all-five measures.
- Contract-v2 labels are synthetic construction proxies. Issue #12 labels remain `independent_ai_review` until qualified humans approve them.
- V8 alone regressed on the main correction benchmark and is not the released model.
- Historical v6 results are useful development evidence but describe a different adapter and backend.
- AuditKIT produced source-model evaluations. Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers, not AuditKIT. CircuitKIT is historical v6 smoke only.
- CircuitKIT evidence covers original v6 compatibility and one bounded activation patch, not a merged-model circuit finding.

## Reproduction and artifacts

See [reproduction instructions](REPRODUCE.md), [SHA256SUMS](SHA256SUMS), [manifest.json](manifest.json), [merge provenance](adapter/merge_provenance.json), and [curated evidence](results/). Raw prediction files are deliberately excluded from this release; aggregate summaries and the separately curated demo payload retain the evidence pointers and hashes.

Team source repository: [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon). Public artifacts: [dataset/evidence bundle](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75), [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08), and [recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html).
