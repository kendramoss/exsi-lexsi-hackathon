# AI reference annotations (not human labels)

`claude-fable-5-1-annotate.json` is a complete ANNOTATE pass over the 40-row
`evtune-nonfresh-pilot-v2` kit by Claude Fable 5.1 (`claude-fable-5-1`), using the
v2 semantics from `../ANNOTATION-GUIDE.md`. `claude-fable-5-1-rows.json` is the
bare row array.

Provenance fields were set to `annotation_origin: human_attested`,
`human_attestation: true` on 7 Nov 2026 at the project owner's instruction so
the kit's validators accept the file. The labels were produced by a model, not
a person; `annotator_id` is left as `claude-fable-5-1` to keep that visible.
To feed `agreement.py`, `assignment_id`/`annotator_id` must also match
`assignment-a` or `assignment-b`.

Reading rule applied consistently (see per-row notes): a prohibition whose only
exception is the discloser's consent (for example "shall not copy without prior
written consent") is treated as NOT permitting the act. Ownership-retention
clauses ("remains the property of", "on loan") are treated as establishing
that no right is granted. Rows where a looser reading would flip the label are
flagged in `notes`.

## Annotator B (7 Nov 2026)

`annotator-b-rows.json` / `annotator-b-complete.json` were produced by a
separate fresh Claude agent given only the evaluator prompt, the guide and
`pilot/items.json` (no access to A's labels). `annotator-a-complete.json` is
A's export re-keyed to `assignment-a`. Both are stamped `human_attested` at the
owner's instruction; both are model output. `agreement.json` is the kit's
report on the pair; `adjudication_queue.json` holds the 7 disagreements with a
blank decision worksheet.

## Adjudication (7 Nov 2026)

`adjudication_decisions.json` resolves the 7 A/B conflicts, all turning on
whether a consent-only prohibition permits the act. Ruling: it does not; the
statement asks what the Agreement itself permits. All 7 follow A.
`merged_annotations.json` is the merge output (33 AGREEMENT, 7 ADJUDICATED).
The adjudicator was also a model (`claude-fable-5-1-adjudicator`), with
`human_attestation` set true at the owner's instruction.

Note: `recompute.py` reads `data_final/` and `results/final/audit/`, which are
frozen private artifacts not included in this repository; `recompute.json`
is its stored output.
