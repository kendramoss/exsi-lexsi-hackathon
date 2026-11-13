# Local product improvement loop

Started: 2026-11-13. Baseline: `f28d9d2a46f85384441792fcbf6984c415e4c38b`.

## Authorized scope

Discover verified product defects and useful small features, implement isolated fixes, run local tests, obtain independent review, and preserve results on feature branches. Do not ask for routine in-scope choices. Work on this machine only.

## Protected boundaries

- Original checkout and other sessions' unfinished worktrees remain untouched.
- Preserve all historical/frozen evidence, labels, model tensors, hashes and source artifacts.
- Do not retrain, launch Kaggle jobs or paid jobs, call teacher models, or choose a replacement model as part of this loop.
- Respect the current recorded decision to use teacher-model labels without a human audit. Teacher agreement is not human validation.
- Do not merge or push main, change deployment infrastructure, submit forms, or delete experiment data.
- Do not invent evidence or treat passing code tests as proof of model-quality improvement.

## Execution

1. Discovery workflow: three read-only lenses (demo behavior, fresh-checkout verification, evidence integrity), each followed by independent verification. At most three findings per lens.
2. Implementation workflow: select high/medium actionable survivors, deduplicate by cause, assign non-overlapping worktrees, test regression first, fix minimally, and independently review.
3. Recheck product state and peer ownership before each next discovery cycle. Do not re-run discovery against unchanged code while workers are pending.
4. Completion notifications are the primary wake signal. A 20-minute scheduled wake is only a fallback while workflows run.
5. Stop active implementation after two discovery passes with no worthwhile new actionable findings; do not manufacture features to keep the loop occupied.

## Current cycle

- Discovery workflow `wf_f4901057-d0d`: complete, nine independently reproduced medium-priority findings.
- Fix/review workflow `wf_110358ab-c72`: running in three non-overlapping isolated worktrees.
- Concurrent narrow discovery `wf_fb383edc-7ca`: inspecting only untouched import/export scripts and schemas; no duplicate audit of active fix lanes.
- Integration branch: `worktree-evidencetune-product-loop`.
- Existing annotated-training, diverse-dialogue and inference-control worktrees are outside this cycle's edit scope.

### Verified findings queued for fixes

| ID | Defect | State |
|---|---|---|
| demo-mobile-evidence-clipped | Mobile reduced-motion conversation clips question/source evidence | Fix/review running |
| demo-space-key-intercepted | Global pager consumes Space on native buttons | Fix/review running |
| demo-mock-run-mislabeled | Mock route displays historical real-run claims and counts | Fix/review running |
| repro-1 | Completed-run validator accepts empty/incomplete/duplicate records | Fix/review running |
| repro-2 | Offline dependency set omits PyYAML, NumPy and safetensors | Fix/review running |
| repro-3 | Pure demo-verifier tests unnecessarily require author-specific raw evidence | Fix/review running |
| EVIDENCE-1 | Saved judge letters can point at different labels after a teacher retry | Fix/review running |
| EVIDENCE-2 | Empty required source tree passes staging without its advertised data | Fix/review running |
| EVIDENCE-3 | Optional audit importer accepts known model exports and mismatched/incomplete exports as human | Fix/review running |

These are code/product correctness findings, not claims that existing recorded model metrics or labels have been changed. No human audit is being requested or performed.
