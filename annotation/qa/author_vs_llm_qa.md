# Annotation agreement

- A: `data/benchmark/{train,dev,test}.jsonl (author key)` (360 labelled)
- B: `annotation/qa/llm_blind_labels.csv` (360 labelled)
- Compared: 360 cases. Status: computed.

| Field | % agreement | Cohen's κ |
|---|---:|---:|
| truth_target | 99.7% | — |
| evidence_sufficiency | 100.0% | 1.0 |
| answerable | 100.0% | 1.0 |
| acceptable_actions | 100.0% | 1.0 |

All four fields agree on 99.7% of cases. Exclusion flags: A 0, B 6.
Disagreements for adjudication: `annotation/qa/author_vs_llm_qa_disagreements.csv`.
