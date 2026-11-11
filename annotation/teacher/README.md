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

The team reviewed all teacher labels and approved them. This was a **review with the labels visible**, not blind relabelling, so it is recorded as sign-off, not as inter-annotator agreement or as the blind audit below. The one pilot row with no teacher label (`row_4d56d6c8143c840c`, tier `needs_human`) still has no label: the teachers and the judge split on whether excerpt 1's written-approval exception means the Receiving Party *may* share with third parties.

## Blind audit of the pilot (ready, not yet done)

[`pilot/audit/annotate.html`](pilot/audit/annotate.html) is an offline audit kit for **31 pilot rows**: all 15 judge-adjudicated rows, the needs-human row, and 15 seeded consensus rows (5 low-confidence). It shows the rows only, with no teacher labels, tiers or rationales. It was built by `teacher/run.py audit-sample` (seed `teacher-audit-v1`).

1. Open `annotate.html` in a browser. Each auditor picks assignment A or B (two auditors give agreement as well; one is enough for an error rate). Don't look at `pilot/labels.jsonl` first.
2. Label all 31 rows, tick the attestation, and export the JSON.
3. Score it against the teacher labels, then regenerate the report:

```bash
python teacher/run.py audit-score annotation/pilot --out teacher/runs/pilot --human path/to/audit_export.json
```

```bash
python teacher/run.py report annotation/pilot --out teacher/runs/pilot
```

`teacher/runs/pilot` is rebuilt by running `label` and `judge` on the pilot, or by copying `pilot/raw_labels.jsonl` and `pilot/judgements.jsonl` from this folder into it. The audit's labels also settle `row_4d56d6c8143c840c`.

## What would make these "validated"

Teacher agreement shows the labels are consistent, not that they are right. The pipeline's blind human audit puts a number on that: every adjudicated and needs-human row plus a seeded sample of consensus rows.

```bash
python teacher/run.py audit-sample annotation/pilot --out teacher/runs/pilot --n 15
```

Until that audit is done, describe these as teacher-labelled with teacher agreement reported, not as human-validated.
