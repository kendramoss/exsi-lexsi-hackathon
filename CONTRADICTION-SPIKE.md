# Contradiction-focused SafeTune spike — 10 Nov 2026

**Decision: KILL_KEEP_MERGED. Retain merged alpha=0.75.** The candidate improved static Contradiction behavior but over-clarified and regressed dialogue utility. No frozen evaluation or public model replacement occurred.

## Protocol

- Started from merged alpha=0.75 (`a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`).
- 96 new non-frozen cases / 480 rows: 80 Contradiction and 16 Entailment controls across six axes, plus 24 training-only replay cases / 120 rows. Total: 600 rows.
- Independent semantic review: GO for all 96 cases / 480 rows. Freshness checks passed. Labels remain synthetic construction proxies.
- One SafeTune PlainSFT continuation: seed 0, one epoch, lr 1e-4, batch 1, gradient accumulation 4, max length 1,024, fp16, gradient checkpointing.
- Selection used existing non-frozen dev only. Kaggle script `367996841` completed 150/150 optimizer steps in 10,887.899 seconds.
- Final candidate adapter SHA-256: `4ba9fce20fb0d4f81c0a4023096a3cf11bdd7c75e7d6335661bc825f29699ce1`.

## Results

| Metric | Merged | Candidate | Delta / gate |
|---|---:|---:|---|
| Semantic overall task success | 96.667% | 98.333% | +1.667pp |
| Targeted overall task success | 90.000% | 92.778% | +2.778pp |
| Pooled Contradiction task success | — | — | **+5.238pp PASS** |
| Contradiction all-five success | — | — | **+19.048pp PASS** |
| Contradiction pair success | — | — | +9.524pp PASS |
| Contradiction action correctness | — | — | +4.762pp PASS |
| Pooled Entailment task success | — | — | −0.952pp PASS |
| Targeted Entailment task success | 93.333% | 91.111% | **−2.222pp FAIL** |
| Resolution overall | 79.167% | 73.529% | **−5.637pp FAIL** |
| Final dialogue task accuracy | 84.766% | 78.125% | **−6.641pp FAIL** |

Complete records, zero evaluation errors, and no non-finite metrics were verified. The three gate violations were `resolution_declined`, `final_dialogue_drop_exceeds_2pp`, and `v8_targeted_dev_yes_task_regression`.

## Behavioral finding

The candidate over-clarified rather than failing at Contradiction semantics:

| Behavior | Merged | Candidate |
|---|---:|---:|
| Unsupported-citation clarification | 18.75% | 53.13% |
| Unnecessary clarification | 6.25% | 25.00% |
| Follow-up model calls | 24 | 68 |
| Fully resolved cases | 20/32 | 7/32 |
| Gold-evidence resolution after clarification | 58.33% | 47.06% |

The Contradiction-heavy continuation lacked equivalent two-turn replay, so static gains came with a shift toward asking for more evidence and losing merged/v8 dialogue behavior.

## Evidence

Output root: `.contradiction_spike/run/367996841/contradiction_spike_output/`.

- Gate: `evaluation/gate.json`, SHA-256 `7eb63ae5e269e109514becf15236c6c336bfd6f6f186dd5229aacedddc842c9a`.
- Summary: `evaluation/summary.json`, SHA-256 `86ab2ef2875001262a81f2470c752dbada379a8db26ff9437d7041886c44c0f9`.
- Worker log SHA-256: `16ee2ff4107b84e4616db7265e01531c8de00e2b7415973dfc4e69cbab96ce23`.
- Complete artifact manifest: `artifact_hashes.json`.

The generated full model and optimizer states were removed after completion to reclaim space. The final adapter, raw predictions, summaries, logs, and provenance remain. Packaging experiments ended in a fully embedded code-and-data notebook; all non-packaging protocol fields remained unchanged.

## Recommendation

Stop. Do not confirm on frozen data and do not replace the public adapter. Subsequent interpolation and routing experiments are separate negative/mixed results, not grounds for adopting this candidate.
