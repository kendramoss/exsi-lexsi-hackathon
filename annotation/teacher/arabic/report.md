# Teacher-label report: `evtune-issue8-arabic-native-review-v1`

Labels by `claude-fable-5-2`, `claude-opus-5-5` (pipeline `teacher-v1`). These are **teacher-model labels, not human labels** (`human_attestation: false`). This kit is **evaluation-only**: its labels must not be used for training.

## Tiers

| Tier | Rows |
|---|---:|
| `teacher_adjudicated` | 6 |
| `teacher_consensus` | 14 |

Low-confidence rows (UNDETERMINED truth or UNCLEAR answerability): 7.

## Teacher agreement (modal labels)

Over 20 rows labelled by every teacher. All fields agree on 70.0%.

| Field | Agreement | Cohen's κ |
|---|---:|---:|
| statement_truth | 90.0% | 0.848 |
| requested_target | 100.0% | 1.0 |
| cited_excerpt | 100.0% | 1.0 |
| citation_status | 95.0% | 0.906 |
| answerability | 90.0% | 0.765 |
| acceptable_actions | 75.0% | 0.635 |

## Self-consistency

Share of a teacher's samples that match its own modal label, averaged over rows.

- `claude-fable-5-2`: 0.975
- `claude-opus-5-5`: 0.9

## Contract-gate failures

- none
