# Raw-base frozen evaluation run plan

## Scope

Descriptive, post-selection baseline only. Generate predictions for `CohereLabs/tiny-aya-global` with no adapter on exactly `semantic_frozen_test` (240 rows) and `v8_targeted_frozen_test` (270 rows), then compare with the already saved v7 and merged alpha=0.75 arms on those same suites. Do not train, tune, rank, reselect, inspect other frozen cases, modify the public model, or run paid jobs.

## Inputs and reuse

- Raw project (read-only): `/Users/anasqumhiyeh/lexsi-koth/evtune`.
- Frozen plan: `/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/local_results/frozen_confirmation/plan.json`.
- Saved arms: `/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/local_results/frozen_confirmation/evaluation/{baseline_v7,merge_alpha_0.75}`.
- Reuse raw-project `local_eval.MPSGenerator`, `local_eval.run_single_turn`, `frozen_confirm.DATASETS`, `frozen_confirm._load_frozen_data`, and `next_run.kaggle_next_flow.summarize_records` without modifying them.
- Generation: Apple MPS, bf16, offline cached Transformers, greedy (`do_sample=false`), 80 new tokens maximum, batch size 8, left padding, identical instruction/input chat messages and strict contract-v2 scoring.

## TDD and execution

- [x] Write tests proving raw-base loading uses no adapter, exact source/label/arm hashes and identities are enforced, and metric recomputation includes explicit denominators and paired deltas.
- [x] Run tests and record the expected import failure before implementation.
- [x] Implement `.base_eval/base_eval.py` with a no-PEFT raw-base loader, frozen input validation, cached commit/tokenizer provenance, prediction generation, and independent summary recomputation.
- [x] Run focused tests in both system Python and the isolated MPS environment, plus the read-only raw-project contract-v2 tests; record counts and logs under `.base_eval/logs/`.
- [x] Generate only the two raw-base views into `.base_eval/predictions/evaluation/raw_base/<view>/` using resume-safe batch files.
- [x] Recompute all three arms from raw predictions; verify row identity, contract-v2 scores, numerators/denominators, all-five case success, and paired deltas. Compare saved summaries to recomputation without rewriting them.
- [x] Record full cached base commit, all tokenizer-file SHA-256 hashes, source/label hashes, saved-arm raw-prediction and plan/summary hashes, software versions, timing, and artifact inventory.
- [x] Write `/Users/anasqumhiyeh/.claude/worktrees/exsi-base-eval/BASE-EVALUATION.md` with exact results, denominators, runtime, caveats, and explicit post-hoc scope.
- [x] Verify final artifacts and clean git state except `.gitignore` and `BASE-EVALUATION.md`; do not commit.

## Execution note

The initial paused process saved 23 semantic batches. The resumed process uses `.base_eval/generation_base_eval.py`, whose SHA-256 exactly matches the locked run plan, and the existing `run_single_turn` resume path validates and reuses completed batches. `logs/resume_batch_hashes.log` captures the original 23 plus the first resumed batch; `logs/resume-reuse-verification.log` confirms all 24 remained byte-identical. Original and resume generation logs are retained separately for active-runtime accounting.

## Metric definitions

For every arm/view, report task success and all five strict metrics: `format_ok`, `action_ok`, `answer_ok`, `whole_window_answer_ok`, and `terminal`, plus case-level all-five task success. `action_ok` excludes solo rows from its denominator; all other row metrics use all rows. All-five success uses cases as denominator and requires five successful rows for a case. Paired deltas are computed row-aligned by input SHA-256 (or case-aligned for all-five), as arm minus raw base, with numerator/denominator and both/only-arm transition counts. These are descriptive paired differences, not significance tests.
