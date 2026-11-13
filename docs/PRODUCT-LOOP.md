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

- Discovery workflow: `wf_f4901057-d0d`.
- Status: running; no findings or product-fix completion claims yet.
- Integration branch: `worktree-evidencetune-product-loop`.
- Existing annotated-training, diverse-dialogue and inference-control worktrees are outside this cycle's edit scope.
