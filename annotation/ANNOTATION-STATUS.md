# Annotation status

**Status as of 6 Nov 2026: kit ready; human annotation not started.**

## Complete

- Frozen source and label SHA-256 values verified against `data_final/FREEZE.json`.
- Default pilot generated from **40 non-fresh cases / 40 correction-dialog rows**, one condition-stratified row per case with shuffled serialized items. No fresh rows, matched siblings, or solo rows are included.
- Offline UI generated with two independent deterministic assignments. Model outputs, source `output` fields, conditions, truth labels, acceptable-action proxies, and all other label metadata are excluded from annotator payloads.
- Independent protocol findings F01–F06 addressed, then aligned to the final normative `evidencetune.task.v2`: ABSENT bare pressure is RETAIN-only, and `ANSWER` is documented as the post-action working answer.
- Condition-order leakage, path collisions, unintended overwrites, UNCLEAR cross-field gaps, draft provenance, and annotator-B note loss have dedicated regressions.
- Human-attested export validation, agreement metrics, conflict queue, blank adjudication worksheet, and merge validation implemented.
- Synthetic unit and CLI workflow tests implemented. Synthetic fixtures are marked `SYNTHETIC_TEST_NOT_HUMAN` and rejected by the normal human-label pipeline.

## Exactly what remains for humans

1. **Two human annotators** must each independently complete all 40 rows in `pilot/annotate.html`, one using A and the other B, and export attested complete JSON. There are currently **zero human annotations**.
2. The coordinator must run `annotation/agreement.py` on those two complete exports. There is currently **no human agreement report**.
3. A human adjudicator must review every disagreement in the generated queue, fill every decision and rationale, set their adjudicator ID, and attest the completed worksheet. There is currently **no human adjudication**.
4. The coordinator must run `adjudicate.py merge` and preserve the audit trail. There are currently **no merged human labels**.
5. Humans should review agreement and ambiguous/truncated cases before any downstream use. High agreement alone does not establish correctness.

## Fresh-set boundary

No fresh-set artifact has been generated or labeled. Later fresh human labeling requires the explicit `--fresh --acknowledge-evaluation-only --output-dir ...` command documented in `ANNOTATION-GUIDE.md`. Fresh text and labels remain evaluation-only: never use them for training, prompting, model selection, or case-level publication.

See `ANNOTATION-GUIDE.md` for exact commands and validation rules.

## 7 Nov 2026 — first custom human-attested export received

`pilot/human_anas.json` and `pilot/assignment_ai_reference.json` contain 40 unique rows and pass `validate_export`: 20 YES / 16 NO / 4 UNDETERMINED truth; 11 SUFFICIENT, 18 INSUFFICIENT, 10 ABSENT, 1 CONTRADICTED; 11 UPDATE-only, 18 RETAIN+CLARIFY, 11 RETAIN-only. The export uses custom assignment `ai-reference`, not assignment A or B. A second independent human export is still required before agreement/adjudication can start.

## 11 Nov 2026 — teacher labels for every kit

All kits (pilot 40, natural 48, Arabic 20) and the template benchmark (360) were labelled blind by Claude Fable 5.2 and Claude Opus 5.5 through the local Claude Code CLI, with judge adjudication of disagreements. Results and caveats: [`teacher/README.md`](teacher/README.md). These are model labels (`human_attestation: false`); the human steps listed above (two blind human exports, agreement, human adjudication) have not been done, and the pipeline's blind human audit (`teacher/run.py audit-sample`) is the cheapest way to put an error rate on the teacher labels.

**Decision, 11 Nov 2026:** the team chose not to run human annotation, agreement or adjudication for the pilot, natural or Arabic kits. Teacher labels with reported teacher agreement are the final labels; they must not be described as human-validated. The pilot's one unresolved row (`row_4d56d6c8143c840c`) is excluded. See [`teacher/README.md`](teacher/README.md#validation-decision-11-nov-2026).
