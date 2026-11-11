# Teacher labels (11 Nov 2026)

Every annotation set was labelled blind by two frontier teacher models, **Claude Fable 5.2** and **Claude Opus 5.5**, run through a local headless Claude Code CLI (no API key). Pipeline and method: [`teacher/README.md`](../../teacher/README.md). These are **teacher-model labels, not human labels**: every label carries `human_attestation: false`. The team reviewed the annotation work and approved labelling everything this way. That review was not blind relabelling, so it is not counted as human agreement.

| Set | Rows | Teacher consensus | Judge-adjudicated | Needs human | Teachers agree (all fields) | In this repo |
|---|---:|---:|---:|---:|---:|---|
| [Template benchmark v1](template-benchmark/REPORT.md) | 360 | 360 match the author key | — | 0 | 99.7–100% per field | all labels |
| [Pilot](pilot/report.md) (`annotation/pilot`) | 40 | 24 | 15 | 1 | 60.0% | all labels |
| [Natural, #25](natural/report.md) (`natural_annotation`) | 48 | 45 | 3 | 0 | 93.8% | report only |
| [Arabic, #23](arabic/report.md) (`arabic_annotation`) | 20 | 14 | 6 | 0 | 70.0% | report only |

Labelling ran 1,177 teacher and judge calls (including retries and the re-label after the fix), about $52 at the CLI's reported list prices.

## What the numbers say

- **Template benchmark:** both teachers, blind, agree with the author key on every evidence-sufficiency, answerability and action label (κ = 1.0) and on every truth target (lenient match). They flagged one real defect, `doc-cause-reason-03` partial evidence, whose outside claim the context refuted. It was reworded and both teachers now agree (`data/benchmark/exclusions.json`).
- **Natural (#25):** high teacher agreement (κ ≥ 0.90 on every field). 11 rows are low-confidence (UNDETERMINED truth or UNCLEAR answerability); these are the rows to look at first in any human review.
- **Pilot:** the teachers disagree systematically, not randomly. Opus is stricter: in 8 rows it allows only RETAIN where Fable also accepts CLARIFY, and in 5 rows it calls the truth UNDETERMINED where Fable says YES. That points at an ambiguity in the guide (when contract text settles a statement, when clarification is acceptable) more than at bad labels. The judge settled 15 rows; 1 needs a human.
- **Arabic (#23):** teachers labelled the semantic fields only. The kit's language-quality assessment (naturalness, register, translation signs) still needs native Arabic reviewers, and #23's "done" condition is native adjudication.

## Why two sets are report-only

The natural and Arabic kits are frozen evaluation sets ("evaluation only … no publication of case-level content") and this repository is public. Their per-row teacher labels are effectively answer keys, so they are kept out of git and shared privately. Their training export is refused by the pipeline in any case.

## Human sign-off (11 Nov 2026)

The team reviewed all teacher labels and approved them. This was a **review with the labels visible**, not blind relabelling, so it is recorded as sign-off, not as inter-annotator agreement or accuracy. On the one pilot row with no teacher label (`row_4d56d6c8143c840c`), the teachers and the judge split on whether excerpt 1's written-approval exception means the Receiving Party *may* share with third parties.

## Validation decision (11 Nov 2026)

The team decided **not to run a blind human audit**. The labels are teacher-model labels, and their quality is reported as teacher agreement (the tables above), not as accuracy. The one pilot row with no teacher label, `row_4d56d6c8143c840c`, is **excluded** from the pilot labels for the same reason.

This also amends the "done" conditions of #25 and #23, which asked for human (and, for #23, native-Arabic) annotation and adjudication.

### How to describe the labels

| OK to say | Not supported |
|---|---|
| "Labelled by two frontier teacher models, Claude Fable 5.2 and Claude Opus 5.5, with disagreements adjudicated by a judge model" | "Human-validated", "human-annotated", "expert-labelled" |
| "Teacher agreement: κ ≥ 0.90 on every field (natural set); 60% full-row agreement (pilot)" | Any accuracy figure for the teacher labels |
| "Arabic rows: semantic labels from teachers; language quality not reviewed by native speakers" | Any claim about Arabic language quality or native-speaker review |
| "The merged model was trained on ContractNLI-derived data with human expert source labels" | "The merged model was trained on teacher-distilled labels" |

### If you change your mind

The blind audit is still ready to run. [`pilot/audit/annotate.html`](pilot/audit/annotate.html) is an offline kit for 31 pilot rows (every judge-adjudicated row, the excluded row, and 15 seeded consensus rows), with no teacher labels shown. After one person labels the rows and exports the JSON, score it:

```bash
python teacher/run.py audit-score annotation/pilot --out teacher/runs/pilot --human path/to/audit_export.json
```

Rebuild `teacher/runs/pilot` first by copying `pilot/raw_labels.jsonl` and `pilot/judgements.jsonl` from this folder into it.
