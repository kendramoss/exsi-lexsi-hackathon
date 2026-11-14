# EvidenceTune: teaching Tiny Aya when a correction deserves to change its mind

**Current model:** `merge_alpha_0.75` = 75% v7 semantic-contrast + 25% v8 targeted/two-turn
**Base model:** Tiny Aya Global, Cohere Labs
**Adapter SHA-256:** `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`

## Summary

A useful assistant should update when evidence settles a correction, resist bare pressure, and ask for decisive evidence when a citation is insufficient. EvidenceTune evaluates that behavior with matched cases rather than word-overlap shortcuts, then trains Tiny Aya Global through CuratorKIT and SafeTune with source-model evaluations in AuditKIT.

Each case has five related rows: valid citation, unsupported citation toward the requested answer, unsupported citation away from it, bare pressure, and solo answering. Valid and unsupported corrections share surface wording while the cited excerpt changes. Training/dev quota packs control TF-IDF overlap, excerpt length, and excerpt position; lexical traps make the distractor at least as similar as the gold excerpt.

## What each toolkit did

- **CuratorKIT** validated and cleaned packs, preserved sidecar labels by input hash, and exported checksums and provenance.
- **SafeTune** trained v7 from 3,115 freshness-filtered historical rows plus 720 reviewed semantic-contrast rows; v8 continued from v7 with targeted/two-turn examples.
- **AuditKIT** produced source-model evaluations and raw predictions. The merged adapter is a CPU weight interpolation, not a new SafeTune run.

**Scorer boundary:** merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers, not AuditKIT. CircuitKIT is historical original-v6 compatibility smoke only.

## Selection and current results

Dev selection compared v7, v8, and three interpolation weights. Only v7 and alpha=0.75 passed the preregistered semantic/targeted retention and resolution gates; alpha=0.75 ranked first.

| Dev metric | v7 | Merged alpha=0.75 |
|---|---:|---:|
| Semantic task success | 94.58% | **96.25%** |
| Targeted task success | 87.22% | **90.00%** |
| Conditional resolution | 38/50 (76.00%) | **27/34 (79.41%)** |
| Final dialogue task accuracy | 81.25% | **83.20%** |

Resolution is conditional on CLARIFY episodes. The 50 and 34 follow-up denominators differ, so these are not same-denominator paired outcomes.

**No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.**

| Frozen confirmation, Apple MPS bf16 | v7 | Merged alpha=0.75 | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five case success | 74.07% | **79.63%** | +5.56pp |

Semantic has 48 cases / 240 rows per arm; targeted has 54 cases / 270 rows per arm. All 1,020 frozen records were checked. A post-selection raw-base arm scored **62/240 (25.83%) semantic** and **65/270 (24.07%) targeted**, with 0/48 and 0/54 all-five successes. v7 scores 213/240 and 247/270. These strict task metrics include format failures (raw-base format success 160/240 and 183/270) and are post-selection descriptive numbers, not general accuracy; the saved arms were not regenerated and their historical software versions are not pinned. This is a descriptive baseline, not a candidate arm. See `BASE-EVALUATION.md`. Current results must not be mixed with historical Kaggle fp16/RTX/vLLM numbers.

The paired case-cluster bootstrap gives merged−v7 semantic task success **+3.75pp [95% CI +0.42, +7.50]** and targeted **+2.22pp [−0.74, +5.56]**. Case-level all-five is +12.50pp [+2.08, +25.00] semantic and +5.56pp [−5.56, +16.67] targeted; the semantic bootstrap interval excludes zero but the exact McNemar test (p = 0.0703125) is not conclusive, and there is no multiplicity correction. See `UNCERTAINTY.md`.

## Reproducing the evidence without hiding source drift

The locked dev plan names original `local_eval.py` SHA-256 `d365ae53b563afaacc7ac7ba31ba0ea13fff3dc218e540a113df47c3bce3034f`. The available frozen-support script has SHA-256 `8ee0ae766af877ba575be6b5e6cfd7d6905ca637fa57712d224f3d76621cfe1c`; the original selection-code bytes could not be recovered. The packaged script is later frozen-support/cache-fixed code and must not be described as the original selection implementation. Historical plan hashes remain unchanged.

The supported check is **raw-record replay**: `release/replay_evidence.py` verifies 55 locked inputs, rescores source/sidecar rows, recomputes all selection gates and frozen headline metrics, and replays all five native-resolution arms. It covers 3,120 single-turn records and the 1,020-record frozen subset. This validates saved evidence, not missing source bytes or fresh generation. Any authorized new generation must use a fresh output root and must never tune on frozen cases.

## Negative results and limitations

- **DPO rejected:** dev semantic task success fell from 96.25% to 94.58%, and resolution from 79.41% to 78.57%.
- **Natural SciFact training rejected:** four reviewed generations retained scope and label ambiguity; do not train or score against that pack.
- **Contradiction weakness:** merged authored-synthetic contradiction task success is 87.2%, versus 96.8% for entailment.
- **Arabic weakness:** v7 and merged both score 62/80 on the small provisional proxy; merged all-five is 4/16 and solo is 4/16. Native-speaker adjudication is absent.
- Labels are synthetic construction proxies or independent AI review. Issue #12 remains `independent_ai_review` until humans approve it. No human or broad natural-domain validation is claimed.
- Historical strict119 is post-hoc sensitivity evidence for original v6, not a newly independent test or a merged-model score.

## Artifacts and licensing

The verified public artifacts are the [merged alpha=0.75 adapter](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75), [data and evidence bundle](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75), [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08), and [recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html). The [kendramoss/exsi-lexsi-hackathon repository](https://github.com/kendramoss/exsi-lexsi-hackathon) is the team submission source. Local release/staging tooling reproduces source/label packs, curated training inputs, raw outputs, plans, logs, scorers, same-run baselines, and immutable source-adapter hashes without performing public actions.

Original EvidenceTune code is **MIT licensed**. The merged adapter is **CC BY-NC 4.0**. Tiny Aya Global is attributed to Cohere Labs. ContractNLI CC BY 4.0, VitaminC CC BY-SA 3.0, AraStance CC BY 4.0, licensed English/Italian XSTest terms, and applicable Lexsi LSAL notices remain separate. Korean XSTest raw rows are excluded from publishable staging because no license was found.
