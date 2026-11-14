# EvidenceTune submission draft

## Project description

EvidenceTune teaches Tiny Aya Global when a correction deserves to change its answer. The target behavior is deliberately narrow: `UPDATE` when cited evidence settles the question, `RETAIN` under unsupported pressure, and `CLARIFY` or `RETAIN` when a citation does not settle it. The project is both a matched-case benchmark and a SafeTune-trained LoRA adapter.

The current candidate is **`merge_alpha_0.75` = 75% v7 semantic-contrast + 25% v8 targeted/two-turn**. Adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.

## Why the benchmark matters

A model can appear evidence-sensitive by matching words or by agreeing with every user. EvidenceTune instead creates five matched conditions from one statement and three excerpts: valid correction, unsupported correction toward the requested answer, unsupported correction away from it, bare pressure, and solo answering. Valid and unsupported rows share surface wording; only the cited evidence changes. Training/dev quota packs balance TF-IDF overlap, excerpt length, and excerpt position cues before minor cleaning drift. Lexical traps specifically make the distractor at least as similar as the gold excerpt.

## CuratorKIT → SafeTune → AuditKIT

- **CuratorKIT** validates and cleans the packs, keeps labels in hash-keyed sidecars rather than trained text, and exports manifests, checksums, and provenance.
- **SafeTune** trains directly from those exports. V7 combined 3,115 freshness-filtered historical rows with 720 reviewed semantic-contrast rows. V8 continued from v7 with targeted and two-turn data. The current model interpolates their LoRA weights; merging performed no additional training.
- **AuditKIT** evaluates source models, saves raw generations, and scores contract behavior and paired comparisons. Contract v2 separates strict format, acceptable action, post-action answer consistency, solo accuracy, all-five case success, and follow-up resolution.

**Custom-scorer boundary:** merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers, not AuditKIT. CircuitKIT is historical v6 smoke only.

This pipeline also exposed two practical toolkit issues: SafeGrad's KL reduction scaled alignment loss by sequence length until replaced with a masked per-token mean, and AuditKIT's callable fingerprint could replay another model's cached results unless the checkpoint path was captured.

## Strongest current results

Selection used **dev only**. Only v7 and alpha=0.75 passed the preregistered semantic/targeted retention and resolution gates; alpha=0.75 ranked first. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.**

| Dev selection | v7 | **Merged α=0.75** |
|---|---:|---:|
| Semantic task success | 94.58% | **96.25%** |
| Targeted task success | 87.22% | **90.00%** |
| Conditional resolution | 38/50 (76.00%) | **27/34 (79.41%)** |
| Final dialogue task accuracy | 81.25% | **83.20%** |

| Frozen confirmation, Apple MPS bf16 | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

Resolution is conditional on CLARIFY episodes; v7 and merged have different follow-up denominators (50 versus 34), so these are not same-denominator paired outcomes. A post-selection raw-base arm scored **25.83% semantic** and **24.07% targeted** on the same suites/backend, with 0/48 and 0/54 all-five successes (v7: 213/240 and 247/270). These strict metrics include format failures, are post-selection and descriptive, and are not same-run with the saved arms (historical software versions unpinned); see `BASE-EVALUATION.md`. Case-cluster bootstrap CIs, discordant counts, and exact tests are in `UNCERTAINTY.md`; the semantic all-five bootstrap CI excludes zero while the exact test (p = 0.0703) is inconclusive, and there is no multiplicity correction.

Semantic evaluation has 48 cases / 240 rows per arm; targeted has 54 cases / 270 rows per arm. All 1,020 frozen raw records were independently checked, and 17 original merge tests passed on 10 Nov 2026. Selection SHA-256: `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b`; frozen summary SHA-256: `3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d`.

A separate 100-case authored synthetic descriptive check gives merged task success of **460/500 (92.0%)**, versus **446/500 (89.2%)** for v7. On 750 safe prompts per model, the merged automated over-refusal proxy is **54/750 (7.2%)**, compared with base **56/750 (7.5%)** and original v6 **53/750 (7.1%)**. This prefix proxy is not a human refusal or answer-quality rate.

## Historical foundation, not the current model

Original v6 established the approach before v7/v8. It improved held-out-document action-routing/behavior consistency from **1/64 to 61/64**, reduced bare-pressure yielding from **64/64 to 0/64**, and reached **103/119 (86.6%)** on strict119 versus **87/119 (73.1%)** for word overlap. Adding topic-diverse VitaminC contrastive data improved strict119 from 91/119 to 103/119 (14–2 discordant pairs; exact McNemar p = 0.004180908203125).

Strict119 is a **post-hoc historical-use sensitivity analysis**, not a newly independent test: 17 originally marked-fresh cases were excluded after measured historical use, and five earlier-pool provenance risks remain. Original v6's safety-retention check found 10 harmful base replies and 6 after SFT among 200 multilingual prompts (Aya Expanse 32B judge). These v6 results used different adapters and Kaggle/RTX/vLLM backends; they are not merged-model scores and must not be mixed into the MPS table.

## Negative results

- **DPO rejected:** dev semantic task success fell from **96.25% to 94.58%** and resolution from **79.41% to 78.57%**. The unchanged merged baseline stayed selected, with no frozen generation.
- **Natural SciFact training rejected:** four data generations and exhaustive review of the surviving 113 cases still found scope and label ambiguity. The pack must not be used for training or scoring; no generation 5.
- **V8 alone rejected as the main correction model:** it regressed on single-turn and frozen task behavior. Only its contribution to the selected interpolation is retained.
- **Historical quote-evidence training rejected:** quoting improved but correction-pair behavior regressed from 115/136 to 101/136 on the original-136 secondary set.
- **No scaling claim:** the 1,000-claim run was cancelled without a checkpoint or evaluation.

## Limitations and claim boundaries

- Current headline results are **contract-v2 synthetic construction-proxy evaluations**, not human validation or broad natural-domain evidence.
- Current comparisons use **Apple MPS bf16**. Historical Kaggle fp16/RTX/vLLM results are not directly comparable.
- The raw-base arm was added **post-selection** and is descriptive only. Resolution rates 38/50 and 27/34 have different conditional denominators.
- AuditKIT produced source-model evaluations; current merged/MPS, Issue10, Arabic, and native-resolution metrics use custom scorers. CircuitKIT is historical v6 smoke only.
- **Contradiction remains weaker:** in the authored synthetic check, merged contradiction task success is **87.2%**, versus **96.8%** for entailment.
- **Arabic remains unresolved:** v7 and merged both score **62/80** on the small provisional proxy; merged all-five success is **4/16** versus v7 **5/16**, and solo accuracy is **4/16**. No native-speaker-validated improvement claim is made.
- Issue #12 labels remain **`independent_ai_review`** until qualified humans approve them. AI/synthetic labels are proxies throughout.
- Five matched rows per case are correlated, not independent observations. The resolution development expansion has 32 non-fresh cases; the four-case v8 pilot was not used for selection.
- CircuitKIT evidence is original-v6 compatibility plus one bounded patch, not a merged-model circuit finding.

## Artifacts

- **Team submission source:** [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon)
- **Public merged adapter:** [Mizore66/evidencetune-merged-alpha-0.75](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75)
- **Public data and evidence:** [Mizore66/evidencetune-merged-data-alpha-0.75](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75)
- **Public collection:** [EvidenceTune merged alpha=0.75](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08)
- **Public recorded-only demo:** [static Hugging Face Space](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html)
- Local rebuild/staging entry points: `.release/evidencetune-merge-alpha-0.75/` and `.public_staging/evidencetune-merged-alpha-0.75/`; both are generated and ignored by Git.
- Article/publication handoff and verified publication provenance: `ABSTRACT.md`, `HF-ARTICLE.md`, `PUBLICATION-CHECKLIST.md`, and `PUBLICATION-RESULTS.json`. The HF Article and final hackathon form remain unpublished/unsubmitted.
- Saved-evidence replay: `release/replay_evidence.py` and `release/evidence-lock.json`
- Licensing: MIT original code, CC BY-NC 4.0 adapter, separate dataset/Lexsi terms in `LICENSE-DECISION.md` and `NOTICE.md`
- Model card and reproduction: `release/MODEL_CARD.md`, `release/REPRODUCE.md`
- Integrity: collection-relative `manifest.json` and `SHA256SUMS`; verifier `release/verify_release.py`
- Curated evidence: `results/merged/`
- Full narrative: `WRITEUP.md`
- Current recorded demo payload: `demo_merged_data.json`; integration contract: `MERGED-DEMO.md`
- Historical recorded demo: `demo.html`, `demo_data.json`, and `DEMO.md`
