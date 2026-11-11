# Teacher labels for template benchmark v1

Teachers `claude-fable-5-2`, `claude-opus-5-5` labelled 360 of 360 cases blind (the annotator sheet view: no condition, no answer key) through the local Claude Code CLI. These are teacher-model labels, not human labels.

| Field | claude-fable-5-2 vs claude-opus-5-5 | claude-fable-5-2 vs author | claude-opus-5-5 vs author |
|---|---:|---:|---:|
| truth_target | 98.9% | 100.0% | 100.0% |
| evidence_sufficiency | 100.0% | 100.0% | 100.0% |
| answerable | 100.0% | 100.0% | 100.0% |
| acceptable_actions | 100.0% | 100.0% | 100.0% |

Truth targets use a lenient match (same normalised text, or one's content words contain the other's).

Flagged for review: 0 case(s) where both teachers reject the author's value for some field, or a teacher asked to exclude the case. Details: `review.json`.
