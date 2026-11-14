# Raw-base evaluation: current contract-v2 frozen suites

## Post-hoc scope

This is a **post-selection, descriptive raw-base baseline only**. It fills the base-to-merged evidence gap on the two already locked confirmation suites; it is not a new candidate arm and does not rerun or revise development selection. The selected public model remains `merge_alpha_0.75`, with locked selection SHA-256 `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b` and adapter SHA-256 `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.

No training, tuning, model selection, ranking, publication, paid job, or public-model alteration was performed. No Kaggle measurements are mixed into this report. No other frozen cases were inspected. These are contract-v2 synthetic/proxy results on only the named suites, not independent human validation, broad natural-domain validation, or evidence of general model performance.

## Locked protocol

- Raw arm: `CohereLabs/tiny-aya-global`, directly loaded with `AutoModelForCausalLM`; **no PEFT import, adapter wrapper, or adapter weights**.
- Cached base commit: `af89d219b53ed9b13b8a4645f9c8028973510324`.
- Local Apple MPS, bf16, offline Transformers; greedy `do_sample=false`, maximum 80 new tokens, batch size 8, left padding.
- The existing raw-project `MPSGenerator` and `run_single_turn` construct exactly the same user messages (`instruction + "\n\n" + input`), apply the same tokenizer chat template, and score with the same strict contract-v2 `evaluate_output` and `summarize_records` code as the saved arms.
- `semantic_frozen_test`: 48 cases, 240 rows, split `frozen_test`.
- `v8_targeted_frozen_test`: 54 cases, 270 rows, split `new_independent_frozen_test`.
- Saved v7 and merged alpha=0.75 predictions were read-only inputs and were not regenerated.

### Dataset hashes

| Suite | Source SHA-256 | Labels SHA-256 |
|---|---|---|
| semantic | `6497061a6706908d9d7dc2d78570d703a265383fcff86e639da6cbb6f8e0880d` | `48906d47d1ee51972af059002ef17fceb087000b0a47f0efc761a0bf0ed42281` |
| targeted | `40c1c9e7e81ad66d965818ba106289186b503ff667206ba8f86a43649307b781` | `c647a8b902489b271fd8b3ae5d0cb3313f3be2ff342f024021ca2c6cb652dc7c` |

### Tokenizer hashes

| File | SHA-256 |
|---|---|
| `tokenizer.json` | `2227ea9c52e8afb3f98bfed2679008b275f2664de69dfde174b374389eb0225d` |
| `tokenizer_config.json` | `fb56a3ef7659346aae196a2ab877355f1e7fd871c36843f709bb2e23c606d972` |
| `special_tokens_map.json` | `2b7ce39630f8a18705331a9b32c3b2236e96e7410791f98a9f8b6494e3ab2ea6` |

## Metric interpretation

Each cell below is `passed/denominator (rate)`. `action_ok` excludes solo rows because solo has no action: its denominator is 192 semantic rows or 216 targeted rows, rather than 240 or 270. Every other row metric uses all rows. `all_five_task_success` is case-level: all five matched conditions must succeed, so its denominator is 48 or 54 cases.

`task_success` requires strict format, an acceptable action where applicable, and the post-action working answer. `answer_ok` is not necessarily whole-window truth. In particular, a behaviorally successful `unsupported_toward` CLARIFY/RETAIN keeps the prior answer and may therefore have `whole_window_answer_ok=false`. `whole_window_answer_ok` is diagnostic, and `terminal` alone is not a quality measure.

Paired differences are **other arm minus the named base arm**, aligned by input SHA-256 for row metrics and by case identity for all-five. They are descriptive differences, not causal attribution or statistical significance tests.

## Semantic frozen results

| Metric | Raw base | v7 | Merged alpha=.75 | v7 − base | Merged − base | Merged − v7 |
|---|---:|---:|---:|---:|---:|---:|
| `format_ok` | 160/240 (0.666667) | 235/240 (0.979167) | 235/240 (0.979167) | +75/240 (+31.250000 pp) | +75/240 (+31.250000 pp) | 0/240 (0.000000 pp) |
| `action_ok` | 85/192 (0.442708) | 172/192 (0.895833) | 181/192 (0.942708) | +87/192 (+45.312500 pp) | +96/192 (+50.000000 pp) | +9/192 (+4.687500 pp) |
| `answer_ok` | 128/240 (0.533333) | 228/240 (0.950000) | 228/240 (0.950000) | +100/240 (+41.666667 pp) | +100/240 (+41.666667 pp) | 0/240 (0.000000 pp) |
| `task_success` | 62/240 (0.258333) | 213/240 (0.887500) | 222/240 (0.925000) | +151/240 (+62.916667 pp) | +160/240 (+66.666667 pp) | +9/240 (+3.750000 pp) |
| `whole_window_answer_ok` | 95/240 (0.395833) | 183/240 (0.762500) | 182/240 (0.758333) | +88/240 (+36.666667 pp) | +87/240 (+36.250000 pp) | −1/240 (−0.416667 pp) |
| `terminal` | 149/240 (0.620833) | 195/240 (0.812500) | 196/240 (0.816667) | +46/240 (+19.166667 pp) | +47/240 (+19.583333 pp) | +1/240 (+0.416667 pp) |
| `all_five_task_success` | 0/48 (0.000000) | 29/48 (0.604167) | 35/48 (0.729167) | +29/48 (+60.416667 pp) | +35/48 (+72.916667 pp) | +6/48 (+12.500000 pp) |

### Semantic paired transitions

Columns `base_only` and `other_only` follow the comparison direction in the first column. Transition counts for every other metric are preserved in `.base_eval/summary.json`.

| Comparison | Metric | Both | Base only | Other only | Neither |
|---|---|---:|---:|---:|---:|
| v7 − raw base | task success | 59 | 3 | 154 | 24 |
| merged − raw base | task success | 60 | 2 | 162 | 16 |
| merged − v7 | task success | 211 | 2 | 11 | 16 |
| v7 − raw base | all-five | 0 | 0 | 29 | 19 |
| merged − raw base | all-five | 0 | 0 | 35 | 13 |
| merged − v7 | all-five | 28 | 1 | 7 | 12 |

## Targeted frozen results

| Metric | Raw base | v7 | Merged alpha=.75 | v7 − base | Merged − base | Merged − v7 |
|---|---:|---:|---:|---:|---:|---:|
| `format_ok` | 183/270 (0.677778) | 266/270 (0.985185) | 266/270 (0.985185) | +83/270 (+30.740741 pp) | +83/270 (+30.740741 pp) | 0/270 (0.000000 pp) |
| `action_ok` | 99/216 (0.458333) | 197/216 (0.912037) | 202/216 (0.935185) | +98/216 (+45.370370 pp) | +103/216 (+47.685185 pp) | +5/216 (+2.314815 pp) |
| `answer_ok` | 136/270 (0.503704) | 262/270 (0.970370) | 263/270 (0.974074) | +126/270 (+46.666667 pp) | +127/270 (+47.037037 pp) | +1/270 (+0.370370 pp) |
| `task_success` | 65/270 (0.240741) | 247/270 (0.914815) | 253/270 (0.937037) | +182/270 (+67.407407 pp) | +188/270 (+69.629630 pp) | +6/270 (+2.222222 pp) |
| `whole_window_answer_ok` | 109/270 (0.403704) | 211/270 (0.781481) | 213/270 (0.788889) | +102/270 (+37.777778 pp) | +104/270 (+38.518519 pp) | +2/270 (+0.740741 pp) |
| `terminal` | 176/270 (0.651852) | 207/270 (0.766667) | 212/270 (0.785185) | +31/270 (+11.481481 pp) | +36/270 (+13.333333 pp) | +5/270 (+1.851852 pp) |
| `all_five_task_success` | 0/54 (0.000000) | 40/54 (0.740741) | 43/54 (0.796296) | +40/54 (+74.074074 pp) | +43/54 (+79.629630 pp) | +3/54 (+5.555556 pp) |

### Targeted paired transitions

| Comparison | Metric | Both | Base only | Other only | Neither |
|---|---|---:|---:|---:|---:|
| v7 − raw base | task success | 62 | 3 | 185 | 20 |
| merged − raw base | task success | 64 | 1 | 189 | 16 |
| merged − v7 | task success | 243 | 4 | 10 | 13 |
| v7 − raw base | all-five | 0 | 0 | 40 | 14 |
| merged − raw base | all-five | 0 | 0 | 43 | 11 |
| merged − v7 | all-five | 37 | 3 | 6 | 8 |

## Descriptive reading and limits

On these two strict synthetic/proxy suites, the raw base has substantially lower task and all-five success than either adapted arm. Strict output-format success is also lower for the raw base (160/240 semantic and 183/270 targeted), so these measurements include contract-following failures and must not be interpreted as a general assessment of the base model. The direct merged-minus-base task deltas are +160/240 semantic and +188/270 targeted; the corresponding all-five deltas are +35/48 and +43/54. The already reported merged-minus-v7 differences remain +9/240 and +6/270 task success, with all-five transitions showing both gains and losses rather than uniform per-case improvement.

These deltas describe only the current frozen predictions. They do not re-open selection, establish statistical significance, or support claims about human preferences, natural-domain performance, or general capabilities. Saved-arm plans specify Apple MPS bf16 but do not pin their historical Python/Transformers versions; those arms were not regenerated. The new raw run used the exact software below.

## Runtime and software

- Hardware: Apple M2 Pro, 32 GB RAM, MPS.
- Python 3.12.16; torch 2.15.0; Transformers 5.22.2; tokenizers 0.23.3; huggingface-hub 2.4.0; safetensors 0.8.0.
- Active runner wall time across original and resumed processes: **1067.1109187602997 seconds** (about 17 min 47 s), including model loads and excluding the pause between processes.
- Original process: 361.89813351631165 seconds and 23 semantic batches. Resumed process: 705.212785243988 seconds, 7 new semantic batches, and 34 targeted batches.
- Sum of logged per-batch generation time: **1042.190 seconds** total; semantic 466.492 seconds and targeted 575.698 seconds.
- Elapsed time including the long external pause: 9538.439174 seconds; this is preserved for audit but is not compute runtime.
- Resume accounting proves 23 completed semantic batches were reused and only 41 batches were generated after resume. The 24 batches present at resume capture remained byte-identical on verification.

## Verification

- **10/10 new focused tests passed** in the actual MPS Python environment (0.073 s): no-adapter loading, exact source/label/saved-arm hashes, strict metric recomputation and denominators, exact view/split restrictions, paired row/case deltas, and post-hoc scope.
- **21/21 existing contract-v2 tests passed** (0.003 s). Total: **31/31 passing tests**.
- Strictly recomputed **1,530 records**: 510 raw-base, 510 saved v7, and 510 saved merged. Every row identity, label, and contract-v2 evaluation matched; all six arm/view summaries exactly matched regeneration.
- Source/label, saved raw prediction/plan/summary, selection, adapter, cached base weight, and tokenizer hashes were verified. Saved raw predictions were not modified.
- Raw prediction SHA-256: semantic `65b69be04e96f802f10eca62ed14b38789194bfd8fa85c6df2b4a9e3735fa971`; targeted `922aa25794b7b1c63574a744a4bbadbeaa4c5a68f6e27e836b3c770ddd625a6d`.

## Artifacts

Paths are relative to this repository. Generated evidence lives under `results/merged/raw_base/`; code and tests under `analysis/raw_base/`.

- Full counts, rates, all paired metrics, and transitions: `results/merged/raw_base/summary.json`
- Run plan: `results/merged/raw_base/run_plan.md`; provenance: `results/merged/raw_base/provenance.json`; runtime: `results/merged/raw_base/runtime.json`
- Dependency inventory: `results/merged/raw_base/environment.txt`; original artifact inventory (absolute source paths from the experiment worktree): `results/merged/raw_base/artifact_inventory.json`
- Code and tests: `analysis/raw_base/` (`generation_base_eval.py` SHA-256 `56cf8793ace373c122604fd798148b64f48d9501c75c3a0281081f95354ae9a0`, matching the run plan)
- Raw semantic and targeted predictions (SHA-256 values above) are not tracked in this repository; they are published as additive public evidence under `evidence/raw_base/` in the model repository.
- Read-only saved arms: `evidence/merged/local_results/frozen_confirmation/evaluation/` in the model repository.

Per-batch files and run-time logs remain in the original experiment worktree; their content is summarized in `summary.json` and `runtime.json`.
