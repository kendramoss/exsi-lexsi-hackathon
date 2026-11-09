# Annotation for the template benchmark v1

Guide: [`docs/annotation-guide.md`](../docs/annotation-guide.md).

## Status

| Split | Labels | Status |
|---|---|---|
| train (180 cases) | author | single-labelled, as #7 allows |
| dev (60 cases) | author | single-labelled, as #7 allows |
| test (120 cases) | author | **needs two human annotators** (blind, then adjudication) |

## Test-split double labelling (to do)

1. Annotator A fills `sheets/test_annotator_A.csv`, annotator B fills `sheets/test_annotator_B.csv`, independently and without seeing model outputs or each other's sheet. Rows use an opaque `item_id` so the condition name in `case_id` is hidden. Do not open `data/` while labelling.
2. Agreement: `python scripts/annotation_agreement.py annotation/sheets/test_annotator_A.csv annotation/sheets/test_annotator_B.csv --out annotation/test_agreement`
3. Adjudicate each row of `annotation/test_agreement_disagreements.csv`, fix `data/families/` if the author key is wrong, add exclusions to `data/benchmark/exclusions.json`, and rebuild.

## Blind LLM QA pass (done, not a substitute for the above)

Three model sub-agents labelled all 360 cases blind (opaque IDs, guide only, no access to the key) to catch authoring errors before human labelling. Results: [`qa/author_vs_llm_qa.md`](qa/author_vs_llm_qa.md).

- Agreement with the author key: 100% on evidence sufficiency, answerability and acceptable actions; 99.7% on truth target. The one miss was a longer wording of the same cause (`doc-cause-reason-04`). All arithmetic matched.
- 6 cases were flagged for a label leak. All were `unsupported_low_overlap` feedback that admitted its own misreading. These 6, plus 1 more of the same pattern, were reworded (see `data/benchmark/exclusions.json`). `qa/llm_blind_labels.csv` shows the labels on the text before that fix.
- A model labeller following the same guide is not independent of the author's labelling logic, so this is **not** inter-annotator agreement and must not be reported as such.
