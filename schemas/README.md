# Data contracts (draft for #2)

JSON Schema (draft 2020-12) for the files every stage hands to the next. **Draft: needs sign-off from the data, ML and frontend owners.**

| File | Schema | Written by | Read by |
|---|---|---|---|
| `cases.jsonl` (one case per line) | [`case.schema.json`](case.schema.json) | Data / CuratorKIT export | runner, metric suite, demo |
| `predictions.jsonl` (one run record per line) | [`run.schema.json`](run.schema.json) (uses [`action.schema.json`](action.schema.json)) | Aya runner + metric suite (#5) | AuditKIT, demo |
| `metrics.json` | [`metrics.schema.json`](metrics.schema.json) | metric suite / AuditKIT | demo, report |

A finished run lives in `results/<run_id>/` with all three files. `cases.jsonl` is copied in so the demo can show the question and context without guessing which export a run used.

Examples: [`examples/cases.example.jsonl`](examples/cases.example.jsonl) (one family: valid / unsupported / bare pressure) and [`examples/predictions.example.jsonl`](examples/predictions.example.jsonl).

## Validate

```sh
pip install jsonschema
python scripts/validate.py                    # examples + demo mock run
python scripts/validate.py results/<run_id>   # a real run dir
python scripts/validate.py --cases path/to/cases.jsonl
```

Besides the schema, the validator checks that every prediction's `case_id` exists, every `policy` has a comparator in `metrics.json`, `run_id` matches, and `case_id` follows `<family_id>__<feedback_condition>`.

## Fields that go beyond #2 (please confirm)

- **`correction_target`** (case): the answer the feedback pushes toward. Without it the metric suite can't tell "moved to the suggested answer" from "drifted somewhere else".
- **`clarification_answer`** (case): the scripted user reply when the model asks for evidence. Null means the user has nothing to add. Needed so clarification can be scored as resolved or not (SPEC: clarification earns credit only when the interaction resolves).
- **`clarification_turn`** (run): the reply plus the model's follow-up, so the demo can show the whole exchange.
- **`score`** (run): per-case flags (`action_acceptable`, `unwarranted_update`, `unnecessary_clarification`, `clarification_resolved`, `final_correct`) written by the metric suite. The demo displays these and never recomputes them.
- **`run_id`, `threshold`, `timestamp`** (run): listed in PLAN.md's run schema but missing from #2.
- `split` allows `smoke` for the 12-case test set.

## Open question for the data owner

SPEC.md says the demo pair uses "identical correction targets". The mock data uses a **mirrored** pair instead: same question and passage; the valid correction moves a wrong answer to the truth, while the unsupported correction tries to move a right answer to a wrong one, using the passage's own words. If the intended design is the same target with different warrant, the schema already supports it (`correction_target` is per case); only the example cases change.
