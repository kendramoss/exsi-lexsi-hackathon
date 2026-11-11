# Teacher-label report: `evtune-natural-dev-frozen-evaluation-v1`

Labels by `claude-fable-5-2`, `claude-opus-5-5` (pipeline `teacher-v1`). These are **teacher-model labels, not human labels** (`human_attestation: false`). This kit is **evaluation-only**: its labels must not be used for training.

## Tiers

| Tier | Rows |
|---|---:|
| `teacher_adjudicated` | 3 |
| `teacher_consensus` | 45 |

Low-confidence rows (UNDETERMINED truth or UNCLEAR answerability): 11.

## Teacher agreement (modal labels)

Over 48 rows labelled by every teacher. All fields agree on 93.8%.

| Field | Agreement | Cohen's κ |
|---|---:|---:|
| statement_truth | 97.9% | 0.967 |
| requested_target | 100.0% | 1.0 |
| cited_excerpt | 100.0% | 1.0 |
| citation_status | 97.9% | 0.963 |
| answerability | 97.9% | 0.939 |
| acceptable_actions | 93.8% | 0.903 |

## Self-consistency

Share of a teacher's samples that match its own modal label, averaged over rows.

- `claude-fable-5-2`: 0.938
- `claude-opus-5-5`: 0.906

## Contract-gate failures

- none
