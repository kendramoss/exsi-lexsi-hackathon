# Capability-routing replay

## Scope and verdict

This is a read-only replay of the specified non-frozen development outputs from run `367996841`. No model was loaded, no output was generated, no training or publication was performed, and no frozen case contents were inspected.

**The saved records exactly support semantic, targeted, and resolution quality scoring for whole-trajectory routing.** They also exactly support follow-up coverage and model-call counts. They do **not** support exact routed token usage or wall-clock latency.

The hypothesis is only partially supported:

- Static routing does not improve overall task success on either pack. Targeted performance is below both individual models.
- Resolution routing improves final dialogue accuracy and fully resolved cases over `contradiction_sft`, with far fewer follow-ups. Final dialogue accuracy remains slightly below `merge_alpha_0.75` alone.
- This is a **two-model harness**, not a replacement adapter. There is no new adapter artifact and no basis for an automatic model-replacement claim.

## Router and exactness

For every aligned row, the replay applies only this observable-action rule:

> If `contradiction_sft`'s parsed initial `ACTION` is `CLARIFY`, select the complete `merge_alpha_0.75` record: its initial output and its own saved dialogue behavior. Otherwise, select the complete `contradiction_sft` record.

Correctness labels, scores, outcomes, and per-case quality play no role in selection. They are used only after selection to aggregate metrics. There is no oracle, per-case best selection, or choice between models based on which one succeeded.

The arms are aligned on input/metadata for static rows and on row/case/condition/split/truth/prior/target for resolution rows. Foreign splits, fresh resolution rows, duplicates, missing rows, and changed source hashes fail closed.

Whole-trajectory selection is important: every reused merged follow-up remains conditioned on the exact selected merged initial output in its saved record. No merged follow-up is attached to a candidate initial state, and no missing follow-up is generated or backfilled. Valid-citation CLARIFYs are scored as initial failures and correctly receive no follow-up under the native protocol.

## Static task success

Each cell reports successes/rows (percentage). Contradiction is truth `no`; Entailment is truth `yes`.

| Pack | Model/harness | Overall | Contradiction | Entailment |
|---|---|---:|---:|---:|
| Semantic dev | contradiction_sft | 236/240 (98.33%) | 119/120 (99.17%) | 117/120 (97.50%) |
| Semantic dev | merge_alpha_0.75 | 232/240 (96.67%) | 115/120 (95.83%) | 117/120 (97.50%) |
| Semantic dev | **routed** | **234/240 (97.50%)** | **118/120 (98.33%)** | **116/120 (96.67%)** |
| Targeted dev | contradiction_sft | 167/180 (92.78%) | 85/90 (94.44%) | 82/90 (91.11%) |
| Targeted dev | merge_alpha_0.75 | 162/180 (90.00%) | 78/90 (86.67%) | 84/90 (93.33%) |
| Targeted dev | **routed** | **161/180 (89.44%)** | **80/90 (88.89%)** | **81/90 (90.00%)** |

Relative to `contradiction_sft`, routed task success changes by −0.83 percentage points (pp) overall on semantic dev and −3.33 pp overall on targeted dev. On targeted dev, it is also 0.56 pp below merged overall: Contradiction is 2.22 pp above merged, but Entailment is 3.33 pp below merged.

### Static action, case, and matched-pair metrics

Action correctness excludes `solo` rows, matching the saved evaluator. Its denominators are 192 overall and 96 per truth slice on semantic dev, and 144 overall and 72 per truth slice on targeted dev.

| Pack | Model/harness | Action accuracy: overall / Contradiction / Entailment |
|---|---|---:|
| Semantic dev | contradiction_sft | 191/192 (99.48%) / 96/96 (100%) / 95/96 (98.96%) |
| Semantic dev | merge_alpha_0.75 | 186/192 (96.88%) / 93/96 (96.88%) / 93/96 (96.88%) |
| Semantic dev | **routed** | **189/192 (98.44%) / 95/96 (98.96%) / 94/96 (97.92%)** |
| Targeted dev | contradiction_sft | 135/144 (93.75%) / 67/72 (93.06%) / 68/72 (94.44%) |
| Targeted dev | merge_alpha_0.75 | 128/144 (88.89%) / 62/72 (86.11%) / 66/72 (91.67%) |
| Targeted dev | **routed** | **129/144 (89.58%) / 62/72 (86.11%) / 67/72 (93.06%)** |

All-five-condition case success, in overall / Contradiction / Entailment order:

| Pack | Model/harness | All-five case success |
|---|---|---:|
| Semantic dev | contradiction_sft | 44/48 (91.67%) / 23/24 (95.83%) / 21/24 (87.50%) |
| Semantic dev | merge_alpha_0.75 | 42/48 (87.50%) / 20/24 (83.33%) / 22/24 (91.67%) |
| Semantic dev | **routed** | **43/48 (89.58%) / 22/24 (91.67%) / 21/24 (87.50%)** |
| Targeted dev | contradiction_sft | 28/36 (77.78%) / 16/18 (88.89%) / 12/18 (66.67%) |
| Targeted dev | merge_alpha_0.75 | 25/36 (69.44%) / 11/18 (61.11%) / 14/18 (77.78%) |
| Targeted dev | **routed** | **24/36 (66.67%) / 13/18 (72.22%) / 11/18 (61.11%)** |

Valid-plus-unsupported-toward matched-pair success, in Contradiction / Entailment order:

| Pack | Model/harness | Pair success |
|---|---|---:|
| Semantic dev | contradiction_sft | 24/24 (100%) / 23/24 (95.83%) |
| Semantic dev | merge_alpha_0.75 | 23/24 (95.83%) / 22/24 (91.67%) |
| Semantic dev | **routed** | **23/24 (95.83%) / 23/24 (95.83%)** |
| Targeted dev | contradiction_sft | 16/18 (88.89%) / 16/18 (88.89%) |
| Targeted dev | merge_alpha_0.75 | 13/18 (72.22%) / 14/18 (77.78%) |
| Targeted dev | **routed** | **14/18 (77.78%) / 15/18 (83.33%)** |

The router sent 57/240 semantic rows (23.75%; 29 Contradiction and 28 Entailment) and 50/180 targeted rows (27.78%; 26 Contradiction and 24 Entailment) to merged.

## Resolution replay

All quality metrics below are exactly recomputed from selected saved records under `evidencetune.resolution.v8`.

| Metric | contradiction_sft | merge_alpha_0.75 | **Routed** |
|---|---:|---:|---:|
| Initial action/task accuracy | 109/128 (85.16%) | 111/128 (86.72%) | **109/128 (85.16%)** |
| Unnecessary clarification on valid rows | 8/32 (25.00%) | 2/32 (6.25%) | **2/32 (6.25%)** |
| Unsupported-row clarification | 34/64 (53.13%) | 12/64 (18.75%) | **10/64 (15.63%)** |
| Gold-evidence resolution | 16/34 (47.06%) | 7/12 (58.33%) | **6/10 (60.00%)** |
| No-evidence resolution | 34/34 (100%) | 12/12 (100%) | **10/10 (100%)** |
| Overall conditional resolution | 50/68 (73.53%) | 19/24 (79.17%) | **16/20 (80.00%)** |
| **Final dialogue task accuracy** | 100/128 (78.13%) | 108.5/128 (84.77%) | **107/128 (83.59%)** |
| Terminal task accuracy | 125/162 (77.16%) | 118/140 (84.29%) | **115/138 (83.33%)** |
| Fully resolved cases | 7/32 (21.88%) | 20/32 (62.50%) | **20/32 (62.50%)** |
| Follow-up calls per resolved follow-up | 1.36 | 1.2632 | **1.25** |
| Scored calls per fully resolved case | 28.0 | 7.6 | **7.4** |

Final dialogue accuracy is 5.47 pp above candidate alone and 1.17 pp below merged alone. The conditional resolution rate is 6.47 pp above candidate and 0.83 pp above merged, but its denominators differ: the router absolutely resolves 16 follow-ups, versus 50 for candidate and 19 for merged, because it clarifies much less often. The higher conditional rate must not be described as a higher absolute number of resolutions.

The candidate emitted CLARIFY on 42/128 initial rows (32.8125%), so those complete rows came from merged. The selected routed behavior has 10 unsupported clarification episodes and 2 unnecessary valid-row clarifications.

## Follow-up coverage, calls, and latency

### Exact follow-up evidence

- Required routed dialogue episodes: **10**, each requiring gold-evidence and no-evidence branches.
- Available valid saved follow-ups: **20/20 (100%)**.
- Reused merged follow-ups: **20**, all attached to their own selected merged initial output.
- Reused candidate follow-ups: **0**.
- Missing or synthesized follow-ups: **0**.

Thus resolution quality and follow-up coverage are computable exactly. There is no need to return single-turn-only findings.

### Model-call accounting

Scored trajectory calls count the selected initial outputs and their follow-ups. Actual harness calls additionally include the candidate's initial call used to make the routing decision, including calls whose outputs are then replaced by merged.

| Pack | Candidate initial | Additional merged initial | Merged follow-up | Actual two-model total | Scored trajectory total |
|---|---:|---:|---:|---:|---:|
| Semantic dev | 240 | 57 | 0 | **297** | 240 |
| Targeted dev | 180 | 50 | 0 | **230** | 180 |
| Resolution dev | 128 | 42 | 20 | **190** | **148** |

For resolution, the routed 20 follow-ups compare with 68 for candidate alone (−48) and 24 for merged alone (−4). However, actual two-model calls are **190**, only 6 fewer than candidate's 196 and **38 more** than merged's 152. The 148 scored trajectory calls exclude the 42 candidate router-pass calls that do not contribute a selected initial output and must not be presented as deployed harness cost.

### Latency and tokens: not computable

Exact routed latency and token totals are **not computable** from these records. Static raw rows have no per-row timing or usage. Resolution records retain only arm-aggregate stage timing/token usage, not the per-row values needed to sum selected trajectories or model the serial candidate-to-merged handoff. Averaging or prorating those aggregates would be an estimate, not exact replay, so this report does not do so.

For context only, the saved single-arm resolution runs report:

| Model | Total seconds | Seconds/model call | Prompt + completion tokens |
|---|---:|---:|---:|
| contradiction_sft | 1620.2047 | 8.2664 | 159,882 |
| merge_alpha_0.75 | 1246.1204 | 8.1982 | 120,995 |

These are not router latency estimates. Fewer follow-ups do not by themselves establish an end-to-end latency win because 42 resolution rows require an additional merged initial call after the candidate router pass.

## Reproduction and tests

From this worktree:

```bash
python3 -I analysis/capability_routing.py \
  /Users/anasqumhiyeh/.claude/worktrees/exsi-contradiction/.contradiction_spike/run/367996841/contradiction_spike_output/evaluation

python3 -I -m unittest discover \
  -s analysis/tests -p 'test_capability_routing.py' -v
```

The replay verifies both single-model saved summaries against record-derived aggregation before reporting routed metrics. All **11 tests pass**, covering action-only selection, non-CLARIFY retention, whole-episode routing, no oracle behavior, alignment/split rejection, missing-follow-up failure, valid-row clarification behavior, and actual two-model call accounting.

## Raw source provenance

Source root:

`/Users/anasqumhiyeh/.claude/worktrees/exsi-contradiction/.contradiction_spike/run/367996841/contradiction_spike_output/evaluation`

The replay checks these SHA-256 values before reading records and never writes to the source files:

| Relative source file | SHA-256 |
|---|---|
| `contradiction_sft/semantic_dev/raw_predictions.json` | `02ef7828b09c99d0b2ee53d89a6fdada4ba4bdb7a06c6808d8631d936663ea88` |
| `merge_alpha_0.75/semantic_dev/raw_predictions.json` | `a5b2e05ea1d02c947d4e9c379565a1ae18c2f56798c67d82ddd3acc7ec109d77` |
| `contradiction_sft/v8_targeted_dev/raw_predictions.json` | `0eb94ef8a0fb50fdc6b35d2d991088244676c0ba2638b27fb680108889356015` |
| `merge_alpha_0.75/v8_targeted_dev/raw_predictions.json` | `f5ab8741964145d408c50fc270bae03ae43a54e6df4b6f8a34858adc66c39032` |
| `contradiction_sft/resolution_dev/resolution_raw.json` | `5132b47227795eb83d0b1338653320b26b593e324e47cc1a1f94fe5d6aca528a` |
| `merge_alpha_0.75/resolution_dev/resolution_raw.json` | `60bd9c98dc81c963e25fb66d03973bb1b50777d69e46eeec6f54490f41809b79` |

These are small development-set, synthetic/proxy results. They justify at most further independent evaluation of a two-model resolution-routing harness; they do not justify replacing the adapter or claiming broad generalization.
