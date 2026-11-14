# EvidenceTune Track 2 — current submission resume, 10 Nov 2026

## Current state

**EvidenceTune is implemented, trained, evaluated, packaged, and publicly available. The current model is `merge_alpha_0.75` (75% v7 + 25% v8), not original v6.** Adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.

The earlier statement that "No EvidenceTune training or fresh 120-case evaluation has run" is obsolete. Original v6 training/evaluation completed on 3–6 Nov; v7/v8 and the merged-model evaluations completed on 8–10 Nov. Initial public model/dataset/collection/demo publication also completed on 10 Nov; the HF Article and final hackathon form remain unpublished/unsubmitted. No paid job was launched for the local packaging pass or this team port.

Verified public artifacts:

- [Merged model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75)
- [Dataset/evidence bundle](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75)
- [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08)
- [Recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html)
- Team submission source: [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon)

### Selected-model evidence

Selection was dev-only. Only v7 and alpha=0.75 passed the preregistered retention/resolution gates; alpha=0.75 ranked first. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.**

| Metric | v7 | **Merged α=0.75** |
|---|---:|---:|
| Dev semantic task success | 94.58% | **96.25%** |
| Dev targeted task success | 87.22% | **90.00%** |
| Dev conditional resolution | 38/50 (76.00%) | **27/34 (79.41%)** |
| Dev final dialogue task accuracy | 81.25% | **83.20%** |
| Frozen semantic task success | 88.75% | **92.50%** |
| Frozen targeted task success | 91.48% | **93.70%** |
| Frozen semantic all-five case success | 60.42% | **72.92%** |
| Frozen targeted all-five case success | 74.07% | **79.63%** |

Frozen evaluation was confirmation-only. All 1,020 raw records were independently verified, and 17 merge tests passed on 10 Nov. Selection JSON SHA-256: `e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b`. Frozen summary SHA-256: `3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d`.

Backend boundary: current selection/confirmation comparisons are Apple MPS bf16. Historical v6 Kaggle fp16/RTX/vLLM results remain useful development evidence but are not directly comparable and are not the current model. Resolution is conditional on different CLARIFY follow-up denominators (50 versus 34), not paired identical opportunities. **A post-selection raw-base arm was evaluated on the same suites/backend; see `BASE-EVALUATION.md` and `UNCERTAINTY.md` for exact results and uncertainty.**

**Custom-scorer boundary:** AuditKIT produced source-model evaluations. Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers, not AuditKIT. CircuitKIT is historical v6 smoke only.

## Selection-code provenance

The locked dev plan names original selection-code SHA `d365ae53…`; available frozen-support code is `8ee0ae76…`, and the packaged script additionally has the later cache fix. Original selection-code bytes could not be recovered. Do not claim exact original-code/hash regeneration. `release/replay_evidence.py` is the supported saved-evidence reproduction path. Any authorized new generation must use a fresh output root and preserve historical raw artifacts.

## Submission package

- `WRITEUP.md`: merged-model headline plus clearly labeled historical v6 evidence.
- `SUBMISSION-DRAFT.md`: concise submission narrative, negative results, limitations, and artifact pointers.
- `release/MODEL_CARD.md`: current adapter card and exact claim boundaries.
- `release/REPRODUCE.md`: offline verification, raw-record replay, source-drift disclosure, and fresh-output-root generation instructions.
- `ABSTRACT.md`, `HF-ARTICLE.md`, `PUBLICATION-CHECKLIST.md`, `PUBLICATION-RESULTS.json`: current article handoff, preparation gates, and verified publication provenance; model/dataset/collection/demo are public, while the HF Article remains unpublished.
- `LICENSE`, `LICENSE-MODEL`, `LICENSE-DECISION.md`, `NOTICE.md`: MIT original code, CC BY-NC 4.0 adapter, and separate dataset/Lexsi terms.
- `.public_staging/evidencetune-merged-alpha-0.75/`: ignored complete local model/dataset collections with source/label packs, raw outputs, scorers, plans, logs, training inputs, baselines, and immutable source-adapter references. Korean raw rows excluded.
- `.release/evidencetune-merge-alpha-0.75/`: generated raw-free package with actual adapter, config, completed adapter-root model card, merge provenance, manifest/SHA256SUMS, curated results, replay validator, and allowlisted source. Ignored by Git.
- `results/merged/`: tracked curated summaries and result documents; no raw prediction dumps.
- `demo_merged_data.json`: new recorded-only v7/merged payload generated from saved predictions.
- `demo.html` + `demo_data.json` + `DEMO.md`: preserved historical v6 demo, payload, and documentation.
- `MERGED-DEMO.md`: frontend integration contract and verification commands.

Offline checks in this worktree: **98 tests total** — 13 release/replay tests, 6 merged-demo tests, 37 annotation tests, 13 natural-annotation tests, 18 merge tests (17 original plus altered-cache rejection), and 11 public-staging tests. Raw replay independently verifies 55 locked inputs, 3,120 single-turn records, and five resolution arms, including native rescoring of every follow-up raw output. The natural suite uses a temporary `natural_data` symlink to the raw source and removes it afterward. The merge mirror also keeps all test temporary files outside the raw project.

## What is genuinely load-bearing

1. **CuratorKIT** validates/cleans packs and emits SFT exports, manifests, checksums, sidecar labels, and provenance.
2. **SafeTune** trains the curated exports. V7 used 3,115 freshness-filtered historical rows + 720 reviewed semantic-contrast rows; v8 continued from v7 with targeted/two-turn data. The merged adapter interpolates their weights without additional training.
3. **AuditKIT** runs and scores source-model evaluations, retaining raw predictions, metrics, paired comparisons, and provenance. Current merged/MPS, Issue10, Arabic, and native-resolution scoring instead uses custom contract-v2/native scorers.

Two historical toolkit fixes remain relevant: SafeGrad's KL scaling was corrected with a masked per-token mean, and AuditKIT's model-cache fingerprint workaround captures the checkpoint path.

## Negative and unresolved results

- **DPO rejected:** semantic dev task success 96.25% → 94.58%; resolution 79.41% → 78.57%. The unchanged merged baseline remains selected. No frozen generation was used.
- **Natural SciFact training rejected:** four generations still have scope/label ambiguity after exhaustive review. Do not train or score against the pack; do not create generation 5.
- **Contradiction weakness:** on the separate 100-case authored synthetic check, merged contradiction task success is 87.2%, versus 96.8% for entailment.
- **Arabic weakness:** v7 and merged both score 62/80 on the small provisional proxy; merged all-five is 4/16 versus v7 5/16, and merged solo is 4/16. Native-speaker adjudication is absent.
- **Human validation absent:** contract-v2 labels are synthetic construction proxies. Issue #12 labels remain `independent_ai_review` until humans approve them. Independent AI review is not human annotation.
- **Over-refusal is proxy-only:** merged 54/750 (7.2%), base 56/750 (7.5%), original v6 53/750 (7.1%). This does not establish equivalence or answer quality.
- **CircuitKIT is v6-only smoke evidence:** one bounded activation patch is not a circuit finding and says nothing directly about merged-model mechanisms.
- Historical strict119 is a post-hoc historical-use sensitivity analysis, not a newly independent test. Five earlier-pool provenance risks remain. Historical seed 2 and scaling claims remain unavailable; the cancelled 1,000-claim run produced no checkpoint/evaluation.

## Historical concept selection

EvidenceTune v4 won the 2 Nov concept-only internal panel: five fresh blind judges preferred it 5/5, mean 56.6/60 versus FaultLine v2 40.6/60. Those are internal concept scores, not official Lexsi predictions or model-performance evidence. EvidenceKey v3's 70-row CuratorKIT→AuditKIT replay remains historical feasibility evidence only.

## Next actions

1. Main agent reviews the team worktree and handles any commit/push; this packaging port does not commit, push, merge, or publish.
2. After main review, the authorized operator may use the already-approved public update path for corrected self-contained cards, collection-relative integrity files, license notices, and dataset metadata. No public update was performed by this port.
3. Verify the ignored package/staging again after any source/document change; rebuild to a new path rather than overwriting an existing release.
4. Submission text should use `SUBMISSION-DRAFT.md` and preserve its proxy/human-validation boundaries.
5. Keep the public recorded demo on `demo_merged_data.json` for the current model and `demo_data.json` explicitly historical. Never combine backends in one scoreboard.
6. Future research, if authorized: qualified human/native-Arabic adjudication and contradiction failure analysis. Do not tune on frozen cases; do not revive rejected DPO/natural SciFact runs without a new evidence gate.

Submission deadline/freeze declaration is **14 Nov 2026 at 23:59 AoE (UTC-12; 15 Nov 2026 at 11:59 UTC)**. HF credit is exhausted; do not launch paid jobs.
