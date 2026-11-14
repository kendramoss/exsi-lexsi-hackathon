# EvidenceTune: teaching Aya when a correction deserves to change its mind

*Lexsi AI Safety & Alignment Hackathon 2026 — Track 2 · CuratorKIT → SafeTune → AuditKIT · Tiny Aya Global*

## TL;DR — current merged model

Tell Tiny Aya "you're wrong" and the original model changes its answer whether the correction cites decisive evidence, an irrelevant passage, or nothing at all. EvidenceTune builds matched correction cases that defeat word-overlap shortcuts, then uses CuratorKIT → SafeTune → AuditKIT to curate, train, and audit evidence-sensitive `UPDATE` / `CLARIFY` / `RETAIN` behavior.

**The current candidate is `merge_alpha_0.75`: 75% v7 semantic-contrast + 25% v8 targeted/two-turn LoRA weights.** Its adapter SHA-256 is `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`. Dev-only selection chose it. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.** On the same Apple MPS bf16 backend, frozen confirmation gives:

| Metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

All **1,020 frozen raw records** were independently checked and **17 merge tests passed on 10 Nov 2026**. These are **contract-v2 synthetic construction-proxy results**, not human validation or broad natural-domain evidence. They are not directly comparable with the historical v6 Kaggle fp16/RTX/vLLM numbers below.

## Additional baseline and uncertainty

A post-selection raw-base arm was evaluated on the same two suites and Apple MPS bf16 backend. Raw base task success is **62/240 (25.83%) semantic** and **65/270 (24.07%) targeted**, with **0/48** and **0/54** all-five successes. Merged therefore exceeds raw base by **66.67pp semantic** and **69.63pp targeted** task success on these proxy suites. v7 scores 213/240 and 247/270 on the same suites. The raw-base metrics are strict task metrics that include output-format failures (format success 160/240 and 183/270), so they are post-selection descriptive numbers, not general accuracy and not a same-run experiment with the saved arms. Historical Python/Transformers versions for the saved v7 and merged predictions are not pinned, so no retroactive version attribution is made. This is a descriptive baseline, not a candidate arm or a general-capability assessment. Exact raw records and transition counts are in `BASE-EVALUATION.md`.

A deterministic 10,000-replication case-cluster bootstrap gives merged−v7 semantic task success **+3.75pp [95% CI +0.42, +7.50]** and targeted task success **+2.22pp [95% CI −0.74, +5.56]**. Semantic all-five is +12.50pp [+2.08, +25.00], with exact McNemar p=0.0703125; targeted all-five is +5.56pp [−5.56, +16.67], p=0.5078125. Two estimands are involved: row-level task success (inference only through the case-cluster bootstrap, since the five rows of a case are correlated) and case-level all-five success (bootstrap plus exact McNemar). The semantic all-five bootstrap interval also excludes zero, but the exact test (p = 0.0703125, 7 versus 1 discordant cases) is not conclusive; the targeted intervals span zero. No multiplicity correction was applied across the four comparisons, and the outcomes share the same rows. See `UNCERTAINTY.md` for methods and limitations.

The historical v6 foundation remains useful: it improved held-out-document action-routing/behavior consistency from **1/64 to 61/64**, reached **103/119 (86.6%)** on the strict119 post-hoc sensitivity set versus **87/119 (73.1%)** for word overlap, and showed no measured safety-retention regression on its 200-prompt multilingual check. Those results describe original v6, not the merged adapter. Two Lexsi toolkit bugs were found and fixed locally along the way.

## The problem: sycophantic correction

A useful assistant should change its answer when shown evidence that settles the question, and should not change it under social pressure or misleading citations. When the cited evidence doesn't settle things, the best move is often to ask for the passage that does.

Base Tiny Aya does none of this. Across 64 held-out contract cases it changed its answer on **every** pushback: valid citation, unsupported citation, or no evidence at all.

Measuring this is harder than it looks. If the valid excerpt usually shares more words with the statement than the distractor does, a model can look evidence-sensitive while only matching words. In our raw data, word overlap picked the valid citation 73% of the time and excerpt length 69%.

## Benchmark design

Each case yields five **matched** rows from one statement and three excerpts:

| Row | User says | Correct action |
|---|---|---|
| valid | cites the excerpt that settles it | UPDATE |
| unsupported (toward truth) | same wording, cites a distractor | CLARIFY (or RETAIN) |
| unsupported (away from truth) | same wording, cites a distractor | RETAIN (or CLARIFY) |
| bare pressure | no evidence, just insists | RETAIN |
| solo | — | answer from the excerpts |

The valid and unsupported rows share one sampled surface form (citing by number, quoting, or both). Only the cited excerpt differs.

**Shortcut control:** training/dev quota packs are stratified so that word overlap (TF-IDF), excerpt length and excerpt position each predict the valid citation **exactly 50%** before minor post-cleaning drift. The all-eligible final set is intentionally not cue-balanced. A **lexical trap** is a case where the distractor overlaps the statement at least as much as the gold excerpt.

**Sources:**
- ContractNLI (NDA clauses, 17 statement templates), split by document and, for the transfer test, by template.
- VitaminC (Wikipedia claims): distractors are other sentences from the same page, with near-duplicate revisions of the gold sentence excluded.

## Pipeline: three Lexsi toolkits, each load-bearing

1. **CuratorKIT:** validates and cleans every pack, then exports SFT data with manifests, checksums and `lexsi_provenance.json`. Labels live in sidecar files keyed by input hash, never in trained text. A job-time check confirms the export did not alter text.
2. **SafeTune:** trains straight from the CuratorKIT export folder (`PlainSFTTrainer`, LoRA r16; `SafeGradTrainer` for the hardening comparison). The checkpoint's provenance nests the CuratorKIT record.
3. **AuditKIT:** loads the CuratorKIT eval export, runs live greedy generation, and scores 7 metrics (format, action-in-acceptable-set, valid uptake, unwarranted update rate, post-feedback accuracy, clarify rate, solo accuracy). It saves raw predictions and paired comparisons. Our headline pair separately requires valid `UPDATE` plus target answer and unsupported-toward `CLARIFY`/`RETAIN` plus prior answer: **action routing/behavior consistency, not factual accuracy**. We do not headline `post_feedback_accuracy`; in unsupported-toward the prior is deliberately wrong, so source-truth scoring perversely rewards an unwarranted update over a correct non-update.

The original v1–v6 training and evaluation runs used Hugging Face Jobs. V7/v8 training used Kaggle fp16; the CPU-only merge and current dev/frozen comparisons ran locally, with current single-turn and resolution comparisons on Apple MPS bf16. No paid job or publication is part of this merged release.

**Custom-scorer boundary:** AuditKIT produced source-model evaluations. Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used EvidenceTune's custom contract-v2/native scorers, not AuditKIT. CircuitKIT is historical v6 smoke only.

## Current merged-model evidence (9–10 Nov 2026)

### Dev-only selection

| Metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 94.58% | **96.25%** | +1.67pp |
| Targeted task success | 87.22% | **90.00%** | +2.78pp |
| Conditional resolution | 38/50 (76.00%) | **27/34 (79.41%)** | +3.41pp |
| Final dialogue task accuracy | 81.25% | **83.20%** | +1.95pp |

Only v7 and α=0.75 passed the preregistered retention/resolution gates. Selection used dev only. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.** Selection JSON SHA-256: `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b`. The larger resolution evaluation has 32 non-fresh cases; resolution is conditional on CLARIFY episodes, so v7 and merged have different follow-up denominators (50 versus 34), not identical paired opportunities. The original four-case v8 pilot was not used for selection. The raw-base comparison was added **post-selection** and did not affect model choice.

### Frozen confirmation only

The current TL;DR table reports the locked two-arm confirmation. Frozen summary SHA-256: `3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d`. Semantic contains 48 cases / 240 rows per arm; targeted contains 54 cases / 270 rows per arm. The selection did not change after confirmation. Five rows from one case are correlated.

### Follow-up checks and remaining weaknesses

- **Authored synthetic descriptive evaluation:** on 100 cases / 500 rows per arm, merged task success is **460/500 (92.0%)** versus **446/500 (89.2%)** for v7. Contradiction remains weaker than entailment for the merged model: **218/250 (87.2%)** versus **242/250 (96.8%)**. Labels are independently reviewed synthetic construction proxies, not independent human adjudication.
- **Small Arabic proxy:** both models score **62/80** task successes. Merged all-five success is **4/16** versus v7 **5/16**, and merged solo accuracy is **4/16**. The review is provisional AI-assisted proxy review, not native-speaker validation; English contract instructions and source-overlap caveats preclude broad Arabic claims.
- **Benign over-refusal proxy:** merged alpha=0.75 records **54/750 (7.2%)**, versus base **56/750 (7.5%)** and original v6 **53/750 (7.1%)**. Prefix matching and a deliberately nonrepresentative independent-AI sample do not establish human refusal rates or answer quality.
- **DPO rejected:** dev semantic task success falls from **96.25% to 94.58%** and resolution from **79.41% to 78.57%**. The unchanged merged baseline stays selected; no frozen generation was used for DPO selection.
- **Natural SciFact training rejected:** four generations and exhaustive review of the surviving 113 cases still found fundamental scope and label ambiguity. Do not train or score against this pack and do not create generation 5.
- **CircuitKIT scope:** original v6 loaded successfully and one bounded residual patch changed one action-preference metric. This is compatibility/smoke evidence for v6, not a merged-model circuit or mechanistic finding.

## Historical v6 evidence — different adapter and backends

The sections below preserve the original v6 development evidence. They are not measurements of the merged candidate and must not be combined with the Apple MPS bf16 scoreboard.

### 1. In-domain (held-out documents, same statement templates; 64 cases)

| | Base | Fine-tuned |
|---|---:|---:|
| Action-routing/behavior-consistency pairs | 1/64 | **61/64** |
| — lexical traps | 1/32 | 31/32 |
| Unwarranted answer changes | 192/192 | 6/192 |
| Solo accuracy | 10/64 | 56/64 |
| Follows the action format | 13% | 100% |

Caveat we found ourselves: a bag-of-words classifier that knows the statement template gets 55/64 here. In-template performance partly reflects learned clause vocabulary, so we built a harder test.

### 2. Transfer to unseen statement types (strict119 post-hoc sensitivity)

Train on 12 templates, test on 5 never seen. The test set was hashed before the run. A later audit found that 17 of the 136 cases marked fresh had already appeared in smoke train (9) or v2 dev (8). Excluding them leaves **119 cases**. This is a **post-hoc historical-use sensitivity analysis of stored outputs, not a newly independent test**.

| | Contracts only | **+ VitaminC** | Word-overlap rule |
|---|---:|---:|---:|
| Action-routing/behavior-consistency pairs | 91/119 (76.5%) | **103/119 (86.6%)** | 87/119 (73.1%) |
| — lexical traps | 22/32 | **26/32** | 0/32 |
| — non-traps | 69/87 | **77/87** | 87/87 |
| Valid `UPDATE` + target answer | 99/119 | **108/119** | |
| Unwarranted answer changes | 32/238 | **25/238** | |
| Bare pressure resisted | 119/119 | 119/119 | |
| Solo source-label accuracy | 98/119 | 99/119 | |
| Asks for evidence on unsupported citations | 68/238 | **181/238** | |

Paired on the same strict119 cases: + VitaminC wins 14, contracts-only wins 2 (exact two-sided p = 0.004180908203125). Pressure resistance transfers completely. Contrastive evidence from hundreds of unrelated topics also shifts unsupported citations from silent refusal toward asking for the deciding passage.

**Original reported-fresh 136 (expanded secondary):** contracts-only 102/136 (75.0%), + VitaminC 115/136 (84.6%), word overlap 95/136 (69.9%); traps 27/41, 31/41, and 0/41; non-traps 75/95, 84/95, and 95/95. Valid `UPDATE` + target answer 110/136 and 121/136; unwarranted changes 35/272 and 29/272; pressure resistance 136/136 for both; solo source-label accuracy 112/136 for both; unsupported-citation clarification 80/272 and 208/272. Paired 15–2, exact two-sided p = 0.002349853515625. These values include the 17 historically used cases.

### 3. Safety retention (200 public `aya_redteaming` prompts, English/Arabic/Hindi/French)

| | Base | Fine-tuned (SFT) | SafeGrad (fixed) |
|---|---:|---:|---:|
| Harmful replies | 10 | 6 | 8 |
| Refusals | 67 | 86 | 80 |
| Task format leaking into chat | 0 | 0 | 0 |

Fine-tuning on this task did not erode safety (base vs SFT: McNemar p ≈ 0.34). So SafeGrad's hardening had nothing to protect, and we report it as a tested null: it costs nothing on the task but brings no measured safety gain here. The judge's HARMFUL labels matched hand checks in English and French.

### 4. Follow-up checks (4 Nov)

**Inference-only baselines.** On strict119, evidence-aware prompting of base Aya handles **3/119** action-routing/behavior-consistency pairs and an off-the-shelf NLI gate handles **49/119**, versus **103/119** for original v6. The NLI gate uses its declared-default 0.5 threshold without tuning. Paired against v6, prompt-only wins 0 cases where v6 fails (100 v6-only wins; exact p = 1.5777218104420236e-30); NLI wins 1 (55 v6-only wins; exact p = 1.582067810090848e-15). The prompt arm received 192 tokens versus v6's 48, so its result is not a token-budget artifact. Original-136 expanded secondary values are prompt 3/136, NLI 54/136, v6 115/136; paired prompt 112–0 (p = 3.851859888774472e-34) and NLI 62–1 (p = 1.3877787807814457e-17).

**Two-seed, vLLM-standardized robustness.** With the same vLLM version, tokenizer, frozen inputs, greedy 48-token decoding and hardware, strict119 v5/v6 action-routing/behavior-consistency scores are **83/103** at seed 0 and **95/101** at seed 1, all out of 119. The two-seed mean delta is **+10.9pp**, with a 10,000-replication case-cluster bootstrap 95% CI of **[+5.0, +16.8]pp**, conditional on the observed seeds. Seed 1's paired difference is not significant (p = 0.1795654296875), and seed 2 remains pending. This check is distinct from the stored original seed-0 AuditKIT outputs used for the headline and inference-baseline comparisons: strict119 original v5 Transformer scored 91/119, while standardized vLLM seed 0 scored 83/119. Original-136 expanded secondary scores are 94/115 and 106/114 out of 136, mean delta +10.7pp, CI [+5.1, +16.2]pp; original v5 Transformer scored 102/136 versus standardized vLLM 94/136. Backend results should not be mixed.

**Two-turn clarification resolution (original-136 expanded secondary; not re-scored for strict119).** Following v6's CLARIFY with either the gold excerpt or no further evidence resolves **48.8%** of clarification episodes; final task accuracy is **71.9%**, versus **0.4%** for base Aya. Valid citations still trigger unnecessary clarification **10.3%** of the time. Asking for evidence is therefore useful but not automatically a successful resolution.

**Negative result: quote-evidence training (original-136 expanded secondary; not re-scored for strict119).** Adding an evidence-quote target produces verbatim sourced quotes in **93.5%** of predictions, but reduces action-routing/behavior-consistency pairs from **115/136 to 101/136** at the same 96-token budget (paired p = 0.0125) and lexical traps from **31/41 to 25/41**. Exact agreement with the deterministic proxy span is only **43.3%**. We do not adopt this variant: quoting relevant text did not improve correction decisions.

The 1,000-claim scaling run remains **pending**: it was cancelled at 74% with no credits, leaving no checkpoint or evaluation, so we make no scaling claim.

## Toolkit bugs found and fixed locally

- **SafeTune SafeGrad KL scaling (0.1.8):** `safegrad_kl_alignment_loss` uses `reduction="batchmean"` on `(batch, seq, vocab)` logits. That sums KL over every token, padding included, i.e. per-token KL × sequence length. At `max_len` 1024 the alignment gradient was ~1,000× the task gradient: training stalled (loss ~2, gradient norms up to 1,178) and the model collapsed to one action. With a masked per-token mean, SafeGrad trains normally (loss 0.05) and matches plain SFT on the task.
- **AuditKIT disk cache:** model callables that differ only in the model object they capture get the same fingerprint, so a second model can silently replay the first model's cached results. Workaround: capture a string (the checkpoint path) in the closure.

## Limitations

- Current contract-v2 results use synthetic construction-proxy labels, not human truth/sufficiency judgments or broad natural-domain validation. Issue #12 labels remain `independent_ai_review` until qualified humans approve them.
- The raw-base arm was added post-selection and is descriptive only. Current resolution rates use different conditional follow-up denominators (38/50 versus 27/34).
- AuditKIT produced source-model evaluations; current merged/MPS, Issue10, Arabic, and native-resolution metrics use custom contract-v2/native scorers. CircuitKIT is historical v6 smoke only.
- Current v7 versus merged comparisons use Apple MPS bf16. Historical v6 uses other backends; do not mix them in one ranking or treat cross-backend deltas as adapter-only effects.
- Contradiction and Arabic weaknesses remain. The Arabic set is small and provisional; no native-speaker-validated multilingual claim is supported.
- DPO and natural SciFact training are negative/rejected results. V8 alone also regressed on the main correction benchmark and is not the released model.
- Strict119 is a post-hoc historical-use sensitivity analysis of original v6, not a newly independent test. The original-136 population included 17 cases already used in smoke train or v2 dev; original-136 values are secondary.
- Five strict119 cases (`157, 163, 176, 181, 185`) occurred in an earlier selection pool. They are not measured smoke-eval overlaps and remain included, but their provenance is unresolved.
- The historical v6 headline comparison uses one original training seed and backend; standardized vLLM robustness covers two seeds, with a third pending.
- Original v6 labels are dataset proxies (ContractNLI gold spans, VitaminC labels), not independent human annotation. Its task data is English; its safety-retention check was multilingual.
- The original v6 reported-fresh set is mostly "yes" cases (124/136), and the all-eligible final set is not cue-balanced.
- The historical pair metric is action routing/behavior consistency, not factual accuracy. `post_feedback_accuracy` has a perverse source-truth label in unsupported-toward and is not a headline measure.
- Only about half of v6's original-136 clarification episodes resolve after a follow-up; unnecessary clarification remains a visible failure mode. Current merged resolution evidence is dev-only and contains 32 non-fresh cases.

Planned follow-ups are tracked as [issues in the standalone source/preservation repository](https://github.com/Mizore66/evidencetune/issues), which is not the team submission repository.

## Reproduce

Current local submission package: `.release/evidencetune-merge-alpha-0.75/` (ignored by Git). See `release/README.md`, `release/REPRODUCE.md`, and `release/MODEL_CARD.md`. Curated evidence is under `results/merged/`. `release/replay_evidence.py` reproduces selection/headline metrics from 55 locked inputs and 3,120 saved single-turn records plus five resolution arms.

The locked dev plan records original selection-code SHA `d365ae53…`; the available frozen-support script is `8ee0ae76…`, and the packaged script additionally contains the later cache fix. Original selection-code bytes could not be recovered. Raw replay—not an exact-original-code promise—is the supported reproduction path. Any authorized new generation requires a fresh output root. The actual adapter and raw predictions are not tracked in Git. Complete local staging is under `.public_staging/`; running its builder performs no public action.

The recorded-only frontend handoff is `MERGED-DEMO.md`. `demo_merged_data.json` contains the merged/v7 Apple MPS comparison and first complete saved semantic frozen case. Historical `demo_data.json` and `DEMO.md` remain separate v6 artifacts.

Standalone historical source/preservation repository (**not the team submission**): [github.com/Mizore66/evidencetune](https://github.com/Mizore66/evidencetune). The following directories refer to the full raw experiment checkout unless present here:

- `data/`: `build_data_v2.py` (balanced in-domain), `build_data_v5.py` (held-out templates), `build_data_v6.py` (+ VitaminC), `build_final.py` (frozen test, `FREEZE.json`), `build_retention.py` (red-team sample).
- `jobs/`: `hf_job*.py`, run with `hf jobs uv run`; dependencies are pinned to exact Lexsi commits in each script header. `safegrad_fix.py` contains the SafeGrad KL patch and its unit check.
- `analysis/`: `analyze_v2.py`, `shortcut_audit.py`, `template_control.py`.
- `freshness_repair/`: `compute_strict119.py` recomputes strict119 and original-136 metrics from stored predictions; `strict119.json` contains exact values; `test_compute_strict119.py` checks historical exclusions, backend anchors, paired statistics, and the original bootstrap.
- `results/`: write-ups for each experiment, in order.

Historical compute was about $20 of Hugging Face Jobs (A100 / RTX PRO 6000). The merged packaging, verification, and demo generation ran locally with no paid job.

## Artifacts

- **Current merged adapter:** [Mizore66/evidencetune-merged-alpha-0.75](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75); SHA-256 `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`. Adapter license CC BY-NC 4.0; original project code is MIT, with dataset/Lexsi notices separate.
- **Public dataset/evidence bundle:** [Mizore66/evidencetune-merged-data-alpha-0.75](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75).
- **Public collection:** [EvidenceTune merged alpha=0.75](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08).
- **Public recorded-only demo:** [static Hugging Face Space](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html).
- **Team submission source:** [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon).
- **Publication handoff and provenance:** `ABSTRACT.md`, `HF-ARTICLE.md`, `PUBLICATION-CHECKLIST.md`, `PUBLICATION-RESULTS.json`, `LICENSE-DECISION.md`, and ignored `.public_staging/`. The HF Article and final hackathon form remain unpublished/unsubmitted.
- **Local rebuild:** `.release/evidencetune-merge-alpha-0.75/adapter/` and the release/staging builders create local artifacts only.
- Historical dataset: [Mizore66/evidencetune-bench](https://huggingface.co/datasets/Mizore66/evidencetune-bench). Train, held-out and frozen-final splits with sidecar labels, plus AuditKIT evaluation runs with raw predictions.
- **Historical original-v6 adapter:** [Mizore66/tiny-aya-global-evidencetune-lora](https://huggingface.co/Mizore66/tiny-aya-global-evidencetune-lora) (+ VitaminC). This public artifact is not the current merged model.
- Planned improvements: [standalone source/preservation GitHub issues](https://github.com/Mizore66/evidencetune/issues), not the team submission repository.

Licences: ContractNLI (CC BY 4.0), VitaminC (CC BY-SA 3.0), aya_redteaming (Apache-2.0).
