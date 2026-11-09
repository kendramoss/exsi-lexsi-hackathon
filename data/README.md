# EvidenceTune data

| Path | What it is | Issue |
|---|---|---|
| [`AUTHORING.md`](AUTHORING.md) | Family record format, authoring rules, split/template allocation | #7 |
| [`../docs/annotation-guide.md`](../docs/annotation-guide.md) | One-page labelling guide | #7 (DA-05) |
| `families/<template_id>.jsonl` | Source of truth: 60 authored families (one fictional source document each) | #7 (DA-03, DA-04) |
| `benchmark/{train,dev,test}.jsonl` | Expanded cases, validated against `schemas/case.schema.json` | #7 |
| `benchmark/checks.{md,json}` | Leakage and lexical-shortcut report | #7 (DA-07) |
| `benchmark/exclusions.json` | Excluded cases with reasons | #7 (DA-06) |
| `smoke/cases.jsonl` | 12-case smoke set: 3 dev families x 4 core conditions | #4 (DA-02) |
| `packs/<name>/` | `messages.jsonl` + `manifest.json` + `checksums.txt` exports | #4, #7 (DA-08) |
| `../annotation/sheets/` | Blank blind-labelling sheets for the two test-split annotators | #7 (DA-06) |
| `../annotation/` | Labelling status, blind LLM QA pass, agreement reports | #7 (DA-06) |

## Rebuild everything

```sh
pip install -r requirements-dev.txt
python scripts/build_cases.py              # families -> benchmark/, smoke/, annotation sheets
python scripts/check_benchmark.py          # leakage + lexical shortcut -> benchmark/checks.md
python scripts/validate.py --cases data/benchmark/test.jsonl
python scripts/export_pack.py build data/smoke/cases.jsonl --out data/packs/smoke
python scripts/export_pack.py verify data/packs/smoke data/smoke/cases.jsonl
python scripts/export_pack.py build data/benchmark/train.jsonl data/benchmark/dev.jsonl data/benchmark/test.jsonl --out data/packs/benchmark-v1
python scripts/export_pack.py verify data/packs/benchmark-v1 data/benchmark/train.jsonl data/benchmark/dev.jsonl data/benchmark/test.jsonl
```

Edit `families/` only; everything under `benchmark/`, `smoke/` and `packs/` is generated.

## Design

- **Families.** Each family fixes the question, context, truth target and one distractor. Six cases vary only the feedback: the four core conditions from #2 (`valid_low_overlap`, `unsupported_high_overlap`, `partial_evidence`, `bare_pressure`) and two lexical-counterbalance controls (`valid_high_overlap`, `unsupported_low_overlap`). Labels per condition are in the annotation guide.
- **Why the controls.** With only the core conditions, valid corrections are always low-overlap and unsupported ones always high-overlap, so a TF-IDF gate tuned in the reverse direction separated them perfectly (test balanced accuracy 1.0 without bare pressure). PLAN.md decision rule 2 says to rebuild the data in that case. The controls put supported and contradicted feedback at both overlap levels.
- **Sources.** Every context is a fictional document written for this benchmark (`CC0-1.0`), so the model cannot answer from memory and licensing is clean.
- **Domains.** `document` and `multihop_table_arith`. No Arabic: issue #7 says to add it only if a native speaker on the team writes the cases.
- **Splits.** One source document per family, and question templates are disjoint across splits (see `AUTHORING.md`): train 30 / dev 10 / test 20 families.

## Current status (checks.md)

- 60 families, 360 cases: train 30 (180), dev 10 (60), test 20 (120). Smoke set: 12 cases.
- Leakage: no `source_id` or `template_id` shared across splits; max cross-split context TF-IDF cosine 0.36.
- Lexical shortcut: on the counterbalanced 2x2, a TF-IDF gate tuned on train scores 0.525 test balanced accuracy, near chance (before the controls, a reverse gate scored 1.0). Across all conditions it scores 0.625 because `partial_evidence` and `bare_pressure` are never updates; reported as a warning.
- Packs `packs/smoke` and `packs/benchmark-v1` round-trip with no field loss and verified checksums.
- Still open: human double-labelling of the test split, agreement, and adjudication (see `../annotation/BENCHMARK-V1.md`); a run through the real CuratorKIT, then `export_pack.py verify` on its output.
