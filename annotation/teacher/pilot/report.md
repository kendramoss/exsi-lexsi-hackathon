# Teacher-label report: `evtune-nonfresh-pilot-v2`

Labels by `claude-fable-5-2`, `claude-opus-5-5` (pipeline `teacher-v1`). These are **teacher-model labels, not human labels** (`human_attestation: false`).

## Tiers

| Tier | Rows |
|---|---:|
| `needs_human` | 1 |
| `teacher_adjudicated` | 15 |
| `teacher_consensus` | 24 |

Low-confidence rows (UNDETERMINED truth or UNCLEAR answerability): 5.

## Teacher agreement (modal labels)

Over 40 rows labelled by every teacher. All fields agree on 60.0%.

| Field | Agreement | Cohen's κ |
|---|---:|---:|
| statement_truth | 85.0% | 0.745 |
| requested_target | 100.0% | 1.0 |
| cited_excerpt | 100.0% | 1.0 |
| citation_status | 97.5% | 0.962 |
| answerability | 87.5% | 0.49 |
| acceptable_actions | 70.0% | 0.571 |

## Self-consistency

Share of a teacher's samples that match its own modal label, averaged over rows.

- `claude-fable-5-2`: 0.963
- `claude-opus-5-5`: 0.9

## Contract-gate failures

- none
