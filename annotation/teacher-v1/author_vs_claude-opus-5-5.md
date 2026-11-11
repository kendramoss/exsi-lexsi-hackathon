# Annotation agreement

- A: `data/benchmark/{train,dev,test}.jsonl (author key)` (360 labelled)
- B: `annotation/teacher-v1/claude-opus-5-5.csv` (360 labelled)
- Compared: 360 cases. Status: computed.

| Field | % agreement | Cohen's κ |
|---|---:|---:|
| truth_target | 70.3% | — |
| evidence_sufficiency | 100.0% | 1.0 |
| answerable | 100.0% | undefined (one label throughout) |
| acceptable_actions | 100.0% | 1.0 |

Field agreement is over 360 cases; 0 rows carried only an exclusion reason. All four fields agree on 70.3% of scored cases. Exclusion flags: A 0, B 0.
Disagreements for adjudication: `annotation/teacher-v1/author_vs_claude-opus-5-5_disagreements.csv`.
