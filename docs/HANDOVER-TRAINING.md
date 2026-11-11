# Handover: train the next EvidenceTune model on the annotated data

*Paste this whole file to your coding agent as its first message. It is written to be self-contained.*

---

You are picking up model training for **EvidenceTune**, a Lexsi Hackathon project (submission deadline **14 Nov 2026 AoE**, target 13 Nov). Repository: `kendramoss/exsi-lexsi-hackathon`, branch from `main`. Data annotation is finished; your job is training and evaluation.

## The task in one paragraph

EvidenceTune teaches a small model, **Tiny Aya Global** (required by the rules), when to change its answer after a user pushes back. It should **update** when the pushback cites evidence that settles the question, **retain** its answer when the pushback is refuted, insufficient or bare pressure, and **clarify** (ask one targeted question about the evidence) when that is acceptable. Read `SPEC.md` and `WRITEUP.md` first. The current release is the merged LoRA `merge_alpha_0.75` (75% v7 + 25% v8 weights), trained with SafeTune on data built from **ContractNLI**; see the README and `release/README.md`.

## What data exists and what you may train on

This is the most important section. Training on evaluation data invalidates the submission's results.

| Data | Where | Labels from | Rows | **Allowed use** |
|---|---|---|---:|---|
| ContractNLI-derived training data (v7/v8) | built by `data/build_data_v*.py` into `data_v*/` (gitignored, not in the repo) | ContractNLI human expert labels | — | **Train** (this is what the release used) |
| Frozen final evaluation | `data/build_final.py` → `data_final/` (gitignored) | ContractNLI | 1,020 records | **Evaluation only**, already used for the frozen confirmation |
| Template benchmark v1, **train** split | `data/benchmark/train.jsonl` | author key, confirmed blind by two teacher models | 180 (30 families × 6) | **Train** |
| Template benchmark v1, **dev** split | `data/benchmark/dev.jsonl` | same | 60 (10 families × 6) | **Model selection** only |
| Template benchmark v1, **test** split | `data/benchmark/test.jsonl` | same | 120 (20 families × 6) | **Evaluation only, once, at the end** |
| Pilot kit | `annotation/pilot/` + labels in `annotation/teacher/pilot/labels.jsonl` | teacher models (Fable 5.2 + Opus 5.5, judge-adjudicated) | 40 (39 labelled) | Train, but small and the teachers disagreed on 40% of rows: use only `label_origin: teacher_consensus` |
| Natural kit (SciFact) | `natural_annotation/` | teacher models | 48 | **Evaluation only. Never train, prompt or select on it.** Per-row labels are private, not in the repo |
| Arabic kit | `arabic_annotation/` | teacher models (meaning only) | 20 | **Evaluation only.** Per-row labels are private |

Ask the project owner for: the `data_v*/` and `data_final/` folders (needed to rebuild the ContractNLI training data and frozen eval), and the private zip of natural/Arabic teacher labels (needed only to *evaluate* on those sets).

### Formats

- **Template benchmark** cases: one JSON object per line, schema `schemas/case.schema.json`. Each case has `question`, `context` (spans `[S1] …`), `original_answer`, `feedback_text`, `feedback_condition`, `truth_target`, `evidence_sufficiency`, `acceptable_actions` (subset of `update`/`retain`/`clarify`), optional `correction_target`, and `clarification_answer`. Six conditions per family; see `data/README.md`. Chat-format exports already exist: `data/packs/benchmark-v1/messages.jsonl` (system, user question+context, assistant original answer, user feedback; the target turn is *not* included; you write it from the labels). Verify a pack with `python scripts/export_pack.py verify data/packs/benchmark-v1 data/benchmark/train.jsonl data/benchmark/dev.jsonl data/benchmark/test.jsonl`.
- **Pilot / natural / Arabic kits** use the task.v2 contract (`annotation/annotation_lib.py`, `validate_annotation`): `statement_truth`, `requested_target`, `cited_excerpt`, `citation_status`, `answerability`, `acceptable_actions` (`UPDATE`/`RETAIN`/`CLARIFY`). For a training-eligible kit: `python teacher/run.py export-train annotation/pilot --out <dir>` (copy `annotation/teacher/pilot/raw_labels.jsonl` and `judgements.jsonl` into `<dir>` first). It refuses evaluation-only kits by design.
- The two formats differ: the template benchmark is question/answer with free-text targets; task.v2 is claim-truth (YES/NO/UNDETERMINED) over contract or paper excerpts. Write a small converter into the training format `local_mps/train.py` expects (a CuratorKIT export at `curated/train/` with `sft_alpaca.jsonl`; see that file) rather than mixing them by hand.

## Existing training code

- `local_mps/train.py {plain|safegrad}` + `local_mps/run.sh`: SafeTune LoRA on Apple MPS; `plain` is ordinary SFT, `safegrad` protects a utility objective. Both use the same data, seed and hyperparameters.
- `jobs/hf_job*.py`: earlier Hugging Face job scripts (v1–v6, final).
- Release and replay tooling: `release/` (`REPRODUCE.md`, `verify_release.py`, `replay_evidence.py`). Note these contain hard-coded paths from one teammate's Mac (`/Users/anasqumhiyeh/...`); pass `--raw-root` or fix them.

## Suggested plan

1. Rebuild the current baseline: get `data_v*/`, reproduce the v7/merged evaluation numbers from `WRITEUP.md` on dev before changing anything.
2. Build a combined training set: ContractNLI training data + template benchmark **train** split (+ pilot consensus rows if you want). Keep the template **test** split, `data_final/`, natural and Arabic out of training and out of model selection.
3. Train ordinary SFT and SafeTune (`safegrad`) on the identical set, same seed/budget (the rules want hardened vs ordinary fine-tuning compared).
4. Select on dev only (ContractNLI dev + template dev). Then run the template **test** split and the frozen sets **once** per final model, and report before/after on more than one metric (the rules require it): valid uptake, unwarranted-update rate, task success, clarification rate.
5. Compare against the current release `merge_alpha_0.75` and against the strongest cheap baseline (evidence-aware prompting). Keep negative results.

## Rules for claims (please keep these exactly)

- Template benchmark, pilot, natural and Arabic labels are **teacher-model labels** (Claude Fable 5.2 + Claude Opus 5.5 with a judge model), **not human-validated**. The team chose not to run a human audit. Don't write "human-annotated", "human-validated" or "expert-labelled" for them, and don't give an accuracy figure for them. Agreement figures are in `annotation/teacher/README.md`.
- The current release was trained on ContractNLI data, not on teacher labels. Only say a model was "trained on teacher-distilled labels" if you actually train one on them.
- Arabic: no claim about language quality or native-speaker review.
- Core model must stay Tiny Aya Global; other models only as teachers, judges or for validation.

## Useful commands

```bash
python scripts/build_cases.py --check          # template benchmark is consistent
python scripts/check_benchmark.py              # leakage and shortcut checks
python3 -m unittest discover -s teacher/tests  # teacher pipeline tests
python3 -I -m unittest discover -s annotation/tests
```

Start by reading `README.md`, `SPEC.md`, `WRITEUP.md`, `data/README.md` and `annotation/teacher/README.md`, then confirm with the owner which data folders you have before training.
