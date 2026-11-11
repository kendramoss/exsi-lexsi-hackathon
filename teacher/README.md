# Teacher labelling: distilling frontier judgement into Tiny Aya

EvidenceTune's student is a small model (Tiny Aya Global). The judgement it has to learn (does this
excerpt actually settle the claim? is this pushback evidence or just pressure?) is something
frontier models do well. This pipeline uses **Claude Fable 5.2 and Claude Opus 5.5 as teachers**
to label blind task.v2 rows, then validates those labels before any of them is used. This is
teacher-model labelling with LLM-judge validation, which the hackathon FAQ allows ("other models
in a supplementary way, such as a teacher model, for validation, or an LLM as a judge"). The core
model stays Tiny Aya.

## What is and isn't teacher-labelled today

| Data | Labels come from |
|---|---|
| Merged-model training and frozen evaluation (`data/build_*.py`, `data_final/`) | **ContractNLI's human expert labels**, turned into dialogue cases by deterministic scripts. Not teacher-labelled. |
| Template benchmark v1 (`data/families/`) | Written and labelled by Claude (Opus 5.5) agents under `docs/annotation-guide.md`, then checked blind by separate Claude instances. Teacher-labelled. |
| `annotation/ai_reference/` | Claude Fable 5.1 and a second Claude agent. Teacher-labelled, but the files are stamped `human_attested` so the kit validators accept them; treat them as model labels. |
| `natural_annotation/fable_5_1_annotations.json` | Claude Fable 5.1 draft. Teacher-labelled. |
| Anything produced by this pipeline | Teacher-labelled, with truthful provenance (`label_origin: teacher_*`, `human_attestation: false`). |

Claims should follow this table: "distilled from frontier teachers" is true for the rows that came
through a teacher, not for the ContractNLI-derived training set.

## How labels are validated

```
blind kit rows ──► label: each teacher × N samples (structured JSON, the kit's own guide)
                     │
                     ▼
                  gate: task.v2 contract (annotation_lib.validate_annotation); refusals, truncations
                     │  and contract violations are recorded and excluded
                     ▼
                  agree: teacher-vs-teacher agreement + Cohen's κ per field; self-consistency
                     │
          ┌──────────┴───────────┐
   teachers agree           teachers disagree / unstable
   teacher_consensus             │
                              judge: picks one candidate label, or AMBIGUOUS
                          ┌──────┴───────┐
                 teacher_adjudicated   needs_human
                     │
                     ▼
                  audit: seeded blind sample (every adjudicated + needs_human row, plus N consensus
                         rows) labelled by humans; exact-match rate per tier with Wilson 95% CI
```

- **Cross-family agreement** (Fable vs Opus) catches one model's idiosyncrasies; **self-consistency** catches unstable labels; the **contract gate** catches impossible combinations no matter how confident the teacher was.
- **The human audit is what turns "two models agree" into a measured error rate.** Report it per tier, e.g. "teacher consensus matched blind human labels on 14/15 audited rows (Wilson 95% 0.70–0.99)". Model labels cannot audit model labels: `audit-score` refuses exports whose annotator is a model.
- **Evaluation-only kits stay evaluation-only.** Teacher labels on `natural_annotation/` and `arabic_annotation/` can score models and pre-screen rows for human review, but `export-train` refuses them. Distillation training data must come from non-frozen sets.
- Arabic: teachers label the semantic fields only. The kit's language-quality assessment (naturalness, register, translation signs) still needs native reviewers (#23).

## Run it

Teachers run through a **local headless Claude Code CLI** (`claude -p`), using the login it already has: no API key, no SDK, nothing to install beyond Claude Code itself. Each call replaces Claude Code's system prompt with the annotation guide, disables every tool, loads no settings, MCP servers or session history, runs in an empty temporary directory, and forces the answer into a JSON schema (`--json-schema`). The teacher sees only the guide and one blind row. `label` and `judge` call the CLI; everything else is offline.

```bash
python teacher/run.py label annotation/pilot --out teacher/runs/pilot
```

```bash
python teacher/run.py judge annotation/pilot --out teacher/runs/pilot
```

```bash
python teacher/run.py report annotation/pilot --out teacher/runs/pilot
```

```bash
python teacher/run.py audit-sample annotation/pilot --out teacher/runs/pilot --n 15
```

After humans label `audit_items.json` blind, score the audit and regenerate the report:

```bash
python teacher/run.py audit-score annotation/pilot --out teacher/runs/pilot --human path/to/human_export.json
```

```bash
python teacher/run.py report annotation/pilot --out teacher/runs/pilot
```

Only for kits that allow training:

```bash
python teacher/run.py export-train annotation/pilot --out teacher/runs/pilot
```

Defaults: teachers `claude-fable-5-2` and `claude-opus-5-5`, 2 samples each, judge `claude-fable-5-2`, effort `high`, 4 parallel CLI processes (`--workers`). Each record keeps the model that actually served it (`served_model`) and the CLI's reported cost. `label` and `judge` are resumable: re-running skips finished rows. Every record stores the prompt and guide SHA-256 so a label can be tied to the exact instructions that produced it.

Cost (measured, Nov 2026): about $0.07 per Opus label and $0.13 per Fable label, so roughly $0.40 per row with the defaults. Try `--limit 2` first and read `report.md` before labelling a whole kit.

The template benchmark (`data/benchmark`, a different label format) has its own blind labeller:

```bash
python teacher/label_template.py --out annotation/teacher/template-benchmark
```

## Outputs (in `--out`)

| File | Contents |
|---|---|
| `raw_labels.jsonl` | Every teacher call: request/served model, prompt and guide hashes, raw output, gate result |
| `judgements.jsonl` | Every judge call and its choice |
| `labels.jsonl` | The distilled label set: one row per labelled item, with `label_origin`, teachers, judge, `low_confidence`, `evaluation_only`, `human_attestation: false` |
| `report.md`, `report.json` | Tiers, teacher agreement and κ, self-consistency, gate failures, audit results |
| `audit_items.json`, `audit_score.json` | Blind audit rows; audit results per tier |
| `train_labels.jsonl` | `export-train` only: consensus, non-low-confidence labels from a training-eligible kit |

## Tests

```bash
python3 -m unittest discover -s teacher/tests
```

The tests use a fake runner, so they check the pipeline's logic (the locked-down CLI command, gating, consensus, judging, tiers, audit, export guards), not any model's labelling quality.
