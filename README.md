# EvidenceTune — Lexsi Hackathon Track 2

A three-person project building a lexical-controlled safety benchmark and SafeTune-trained Aya adapter for evidence-sensitive correction.

EvidenceTune teaches and evaluates when a model should accept supported feedback, resist unsupported correction, or request clarification while preserving final task utility.

**Official fit:** Track 2a #2 (safety benchmark), with Track 2b #5 (safety-hardened versus ordinary fine-tuning) as the secondary comparison.

**Pipeline:** CuratorKIT → SafeTune → AuditKIT.

## Current merged-model submission

**Selected release (10 Nov 2026): `merge_alpha_0.75`**, a CPU-only interpolation of **75% v7 semantic-contrast + 25% v8 targeted/two-turn LoRA weights**. The merge performed no additional training.

Adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.

### Public artifacts

- [Merged alpha=0.75 model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75)
- [Merged model data and evidence](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75)
- [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08)
- [Recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html) — replays saved predictions; it does not run a model.

### Frozen confirmation results

Selection used **dev data only**; the frozen suite was confirmation-only and did not change the selected model. Both arms below ran on the same **Apple MPS bf16 Transformers** backend.

| Frozen metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

Semantic evaluation contains 48 cases / 240 rows per arm; targeted evaluation contains 54 cases / 270 rows per arm. All 1,020 frozen raw records were independently checked. These are **contract-v2 synthetic construction-proxy results**, not human validation or broad natural-domain evidence.

### Evidence and reproducibility

- [Submission draft](SUBMISSION-DRAFT.md) and [full write-up](WRITEUP.md) document selection, results, negative results, and claim boundaries.
- [Release tooling](release/README.md) and [reproduction instructions](release/REPRODUCE.md) cover package verification, saved-record replay, adapter interpolation, and demo regeneration. The supported evidence path is raw-record replay, not a promise to recover missing original selection-code bytes.
- [Curated merged-model evidence](results/merged/) contains summaries and locked selection/confirmation metadata without raw prediction dumps.
- [Demo integration contract](MERGED-DEMO.md), [recorded payload](demo_merged_data.json), and [payload builder](demo/build_merged_demo.py) define the current recorded-only comparison. The [historical v6 demo](DEMO.md) is separate and must not be relabelled or mixed into the merged-model scoreboard.

### Licenses and limitations

Original EvidenceTune code is [MIT licensed](LICENSE); the merged adapter is [CC BY-NC 4.0](LICENSE-MODEL). Dataset, prompt, base-model, and Lexsi toolkit terms remain separate; see the [license decision](LICENSE-DECISION.md) and [third-party notices](NOTICE.md).

- Current merged/MPS scores use EvidenceTune's custom contract-v2/native scorers, **not AuditKIT**. CircuitKIT evidence is historical v6 compatibility smoke only.
- Current Apple MPS bf16 results are not directly comparable with historical v6 Kaggle fp16/RTX/vLLM results.
- Raw base Tiny Aya was not evaluated on the current contract-v2 suites, so base→merged correction improvement is unmeasured. Five rows from one case are correlated, and current resolution rates have different conditional follow-up denominators.
- Contradiction and Arabic weaknesses remain; the small Arabic proxy is not native-speaker validation. DPO and natural SciFact training were rejected. Historical v6 safety-retention results are not merged-model safety evidence.

## Run the demo locally

```sh
cd demo
python -m http.server 8000
# then open http://localhost:8000
```

The repository frontend includes a separately labeled invented smoke example. The live public demo linked above replays the verified merged-model predictions.

## Project documents

- [Research specification](SPEC.md)
- [Written execution plan](PLAN.md)
- [Task backlog](BACKLOG.md)

### Task categories

- **Data & Annotation** — sources, counterfactuals, independent labels, Arabic quality, and CuratorKIT.
- **ML & Evaluation** — Aya runners, SafeTune, baselines, AuditKIT, and analysis.
- **Frontend & Design** — demo experience, visual communication, and presentation.
