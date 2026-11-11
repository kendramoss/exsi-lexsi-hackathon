# Annotation for the template benchmark v1

This covers the 60-family template set in `data/families/` only. It uses [`docs/annotation-guide.md`](../docs/annotation-guide.md) and `scripts/annotation_agreement.py`. The task.v2 and natural sets use the kit in this folder ([ANNOTATION-GUIDE.md](ANNOTATION-GUIDE.md), `agreement.py`), which has a different label set; don't mix the two.

Guide: [`docs/annotation-guide.md`](../docs/annotation-guide.md).

## Status

| Split | Labels | Status |
|---|---|---|
| train (180 cases) | author | single-labelled, as #7 allows |
| dev (60 cases) | author | single-labelled, as #7 allows |
| test (120 cases) | author | **needs two human annotators** (blind, then adjudication) |

## Teacher labels (done, 11 Nov 2026)

All 360 cases were labelled blind by Claude Fable 5.2 and Claude Opus 5.5 (local Claude Code CLI). Both agree with the author key on every evidence, answerability and action label; see [`teacher/template-benchmark/REPORT.md`](teacher/template-benchmark/REPORT.md). These are model labels: the human double labelling below is still what #7 asked for.

## Test-split double labelling (not done, by decision)

On 11 Nov 2026 the team chose teacher labels over human double labelling (see [`teacher/README.md`](teacher/README.md#validation-decision-11-nov-2026)). The blank sheets in `sheets/` and `scripts/annotation_agreement.py` remain available if human labels are wanted later.

## Blind LLM QA pass (done, not a substitute for the above)

Three model sub-agents labelled all 360 cases blind (opaque IDs, guide only, no access to the key) to catch authoring errors before human labelling. Results: [`qa/author_vs_llm_qa.md`](qa/author_vs_llm_qa.md).

- Agreement with the author key: 100% on evidence sufficiency, answerability and acceptable actions; 99.7% on truth target. The one miss was a longer wording of the same cause (`doc-cause-reason-04`). All arithmetic matched.
- 6 cases were flagged for a label leak. All were `unsupported_low_overlap` feedback that admitted its own misreading. These 6, plus 1 more of the same pattern, were reworded (see `data/benchmark/exclusions.json`). `qa/llm_blind_labels.csv` shows the labels on the text before that fix. After an independent review, about 95 valid/unsupported texts were then rewritten to balance length and context reuse (see `data/README.md`), so this QA pass predates them; the human test-split labelling below is what validates the current text.
- A model labeller following the same guide is not independent of the author's labelling logic, so this is **not** inter-annotator agreement and must not be reported as such.
