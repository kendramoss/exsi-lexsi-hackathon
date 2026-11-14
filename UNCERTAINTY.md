# Paired frozen-evaluation uncertainty

Scope: saved `merge_alpha_0.75` versus `baseline_v7` predictions only. No model was trained, selected, or replaced.

## Claim table

Claims are limited to observed paired differences in these synthetic-proxy evaluations; the table does not establish superiority, generalization, or readiness for replacement.

| Frozen view | Outcome | Merged | v7 | Delta, pp (95% CI) | Discordant: merged-only / v7-only | Exact McNemar p |
|---|---|---:|---:|---:|---:|---:|
| `semantic_frozen_test` | Task success (rows; case-cluster inference) | 222/240 (92.50%) | 213/240 (88.75%) | +3.75 [+0.42, +7.50] | 11 / 2 | not applicable |
| `semantic_frozen_test` | All-five case success (cases) | 35/48 (72.92%) | 29/48 (60.42%) | +12.50 [+2.08, +25.00] | 7 / 1 | 0.0703125 |
| `v8_targeted_frozen_test` | Task success (rows; case-cluster inference) | 253/270 (93.70%) | 247/270 (91.48%) | +2.22 [-0.74, +5.56] | 10 / 4 | not applicable |
| `v8_targeted_frozen_test` | All-five case success (cases) | 43/54 (79.63%) | 40/54 (74.07%) | +5.56 [-5.56, +16.67] | 6 / 3 | 0.5078125 |

Deltas and confidence limits are percentage points (pp), calculated as merged minus v7. Task-success denominators are 240 or 270 rows per arm; all-five denominators are 48 or 54 cases per arm.

## Exact method

- Paired rows by `(case_id, condition)` after requiring identical input text and metadata/labels across arms. Each case has exactly five declared conditions; all six overall frozen summary metrics and their denominators were reproduced from the raw records.
- Task success is the mean of row-level `evaluation.task_success`. All-five case success is true only when all five rows for that case have task success.
- For each view and both outcomes, drew 10,000 bootstrap replications with seed 20261111. Each replication sampled the view's cases with replacement and carried all five paired rows together. The 95% percentile CI uses linear interpolation at `(B - 1) * p` for `p = 0.025` and `0.975`.
- Exact two-sided McNemar uses the symmetric binomial distribution on all-five discordant cases (doubling the smaller tail, capped at one). Row-level task-success discordant counts are descriptive; a row-wise McNemar test is not applicable because five rows per case are correlated.
- No naive matched-resolution comparison was computed because clarification denominators differ.

## Limitations

- Labels are synthetic proxies by construction, without independent human sufficiency annotation; these are not human judgments or validated real-world outcomes.
- Only 48 and 54 case clusters are available. The bootstrap describes sampling variability across observed cases, not training-run, model-selection, prompt, hardware, or backend variability.
- Predictions come from local Apple MPS bf16 Transformers runs. Results are conditional on that backend and these fixed greedy predictions.
- Four outcome/view comparisons are reported without multiplicity adjustment. Bootstrap intervals are approximate; exact McNemar applies only to all-five case success.
- The targeted view is a separate targeted frozen set, not an independent replication of the semantic view. No public model replacement or new model-quality claim follows from this analysis.

## Provenance

SHA-256 hashes for every raw prediction, summary, and plan file, deterministic numerical results, and analysis provenance are in ignored `.uncertainty/`. The frozen source records were read only.
