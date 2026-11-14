# Claims and sources

Paths are relative to the repository root. Rows marked "recomputed" are recomputed by [`check_kit.py`](check_kit.py).

| Spoken or shown claim | Value | Source | Verified |
|---|---|---|---|
| Historical comparison is plain training (v5, contracts only) vs EvidenceTune v6 | 136 cases, 544 pushbacks, `final-fresh` | `DEMO.md`, `docs/demo-flow.md`, `demo/data/results/final-fresh/metrics.json` | recomputed (544 case rows, 136 families) |
| Plain training asks for the source on wrong quotes | 80 / 272 | `demo/data/results/final-fresh/predictions.jsonl`, policy `ordinary_sft`, condition `unsupported_high_overlap`, action `clarify` | recomputed |
| EvidenceTune v6 asks for the source on wrong quotes | 208 / 272 | same file, policy `safetune` | recomputed |
| Chosen chat example (excerpt 3 about returning copies): plain training switches, EvidenceTune asks | family `c004`: `ordinary_sft` update, `safetune` clarify | `final-fresh` cases and predictions | recomputed |
| Merged alpha=0.75 semantic task success | 222/240 = 92.5% | `demo_merged_data.json` `scoreboards.semantic_frozen_test`; `MERGED-DEMO.md`; `README.md` | recomputed |
| Merged alpha=0.75 targeted task success | 253/270 = 93.70% | `scoreboards.v8_targeted_frozen_test` | recomputed |
| v7 semantic and targeted, same backend (local Apple MPS bf16) | 213/240 = 88.75%; 247/270 = 91.48% | same | recomputed |
| Merge is 75% v7 + 25% v8, no extra training | description | `README.md` "Selected release" | read |
| Proxy scope, recorded only | contract-v2 synthetic construction-proxy; `recorded_only: true` | `demo_merged_data.json`; `MERGED-DEMO.md` | recomputed |
| Teacher labels, no human audit, by team decision | description | `README.md` teacher paragraph; `docs/HANDOVER-TRAINING.md` | read |
| Local page does not show merged outputs | page says the merged model has "its own frozen results" | `demo/index.html`, `demo/README.md` | read |

## Not narrated: post-selection descriptive evidence, not yet merged to main

Raw-base and paired-uncertainty analyses (`exsi-base-eval/BASE-EVALUATION.md`, `exsi-uncertainty/UNCERTAINTY.md`) are being synchronized independently and are not on main. This kit does not use them in narration. If they merge before recording, show them only as post-selection and descriptive. For reference, as read from those read-only files: raw base task success 62/240 semantic and 65/270 targeted; merged minus v7 +3.75 pp (95% CI +0.42 to +7.50) semantic and +2.22 pp (CI -0.74 to +5.56, includes zero) targeted. Until merged, do not say base-to-merged improvement was measured on main.

## Excluded claims

No claim of safety, natural-domain or Arabic performance, human validation, general correction ability, or model superiority. Labels are proxies. Historical v6 numbers and merged numbers come from different suites, scorers and backends and must never be compared with each other.
