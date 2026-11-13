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
- Fix/review workflow `wf_110358ab-c72`: stopped after overlapping execution was detected; source changes and tests preserved read-only for recovery.
- Concurrent narrow discovery `wf_fb383edc-7ca`: complete; independently reproduced two export integrity defects.
- Replacement completion/review workflow `wf_6e8010c5-b79`: offline verification, evidence integrity and export fixes passed independent review and were integrated. Demo completion hit a provider 429; work was preserved.
- Demo finish/review workflow `wf_f0404fa7-229`: complete and approved; three demo fixes integrated.
- Post-fix discovery `wf_5f3f3567-3dd`: demo pass was clear; static review found template-label retry loss. Coordinator reproduced four failing assertions with fake runners, fixed the completion filter, and passed all 22 teacher tests.
- Final independent sweeps `wf_8721166c-db9`: complete; two bounded independent passes found no further release-blocking actionable defects. Active discovery/fix execution is complete, rather than repeatedly scanning unchanged code.
- Integration branch: `worktree-evidencetune-product-loop`.
- Existing annotated-training, diverse-dialogue and inference-control worktrees are outside this cycle's edit scope.

### Verified findings queued for fixes

| ID | Defect | State |
|---|---|---|
| demo-mobile-evidence-clipped | Mobile reduced-motion conversation clips question/source evidence | Fixed; independently reviewed |
| demo-space-key-intercepted | Global pager consumes Space on native buttons | Fixed; independently reviewed |
| demo-mock-run-mislabeled | Mock route displays historical real-run claims and counts | Fixed; independently reviewed |
| repro-1 | Completed-run validator accepts empty/incomplete/duplicate records | Fixed; independently reviewed |
| repro-2 | Offline dependency set omits PyYAML, NumPy and safetensors | Fixed; independently reviewed |
| repro-3 | Pure demo-verifier tests unnecessarily require author-specific raw evidence | Fixed; independently reviewed |
| EVIDENCE-1 | Saved judge letters can point at different labels after a teacher retry | Fixed; independently reviewed |
| EVIDENCE-2 | Empty required source tree passes staging without its advertised data | Fixed; independently reviewed |
| EVIDENCE-3 | Optional audit importer accepts known model exports and mismatched/incomplete exports as human | Fixed; independently reviewed |
| export-partial-overwrite | Failed external-input export overwrites messages but leaves stale manifest/checksums | Fixed; independently reviewed |
| export-duplicate-identities | Export verifier silently collapses conflicting duplicate IDs | Fixed; independently reviewed |
| template-failed-resume | Template teacher labeller treats failed/refused/truncated labels as finished and silently never retries them | Fixed; independently reviewed |

These are code/product correctness findings, not claims that existing recorded model metrics or labels have been changed. No human audit is being requested or performed.

## Integrated verification checkpoint

Local integration commits: `143a567` (offline verification), `4079087` (teacher/staging integrity), `a951580` (export safety), `adbdf20` (demo).

Fresh coordinator verification: 35 scripts tests, 19 teacher tests using fake clients, 14 staging tests including complete bundle/hash/replay checks, 13 release/replay tests, 6 demo Python tests with explicit raw-evidence mode, and 4 Node mapping tests: **91 tests passed**. In addition, **9 real-Chrome regression groups passed** for keyboard, mobile visibility, route provenance, and offline requests. Default demo mode runs its four pure tests and explicitly skips only the two evidence integrations; explicit evidence mode ran all six successfully. No teacher model or inference was called.

The additional template-resume fix `b6312a5` passed three new offline tests and all 22 teacher tests. Across the integrated scope this totals **94 distinct passing tests**, plus the 9 Chrome regression groups. Two final independent sweeps approved the scope without further blocking findings.

The reviewers additionally checked that all 16 saved pilot judgments remain reusable and all 39 saved label objects are unchanged. Clean dependency installation/minimum-version resolution, real human auditing, non-Chrome browsers, and live model performance were not tested.

Known non-blocking backlog: `demo/tests/check-merged-page.mjs` is a legacy browser script with an obsolete badge expectation for the current historical default route. It is not used by the verified historical-page regression suite and was already stale at baseline; it was not represented as passing. The current merged payload mapping and hash/regeneration checks did pass. This pass does not claim all repository tests work without their documented external evidence roots.

### Coordination incident

Directly messaging an active workflow child resumed a second execution against the evidence lane's allocated worktree. That duplicate execution was stopped after it reported concurrent source edits; its added regression tests were preserved. Do not send further direct continuation messages to active workflow children. Await the workflow's own completion/review output and inspect the final diff before integration. This incident did not authorize edits to any other session's data, labels, or model artifacts.
