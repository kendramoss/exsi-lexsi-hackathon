# Arabic native-review coordinator README

## Status and scope

This directory is an **uncompleted blind review kit**, not human/native-validated annotation. The builder selected one condition-balanced correction-dialog row from each of the 20 existing Arabic evaluation cases. It created no Arabic case content, changed no frozen source, performed no model inference, and made no semantic review decision.

Issue **#8 remains open**. The project still needs independently authored data and later evaluation; this review kit does not satisfy either requirement. Do not promote these rows or any future exports to validated gold merely because the kit builds or reviewers agree.

## Files

- `annotate_a.html`: offline RTL workbench containing **only assignment A**; distribute only to reviewer A.
- `annotate_b.html`: offline RTL workbench containing **only assignment B**; distribute only to reviewer B.
- `ANNOTATION-GUIDE.md`: Arabic/bilingual semantic and language-review instructions, AraStance attribution, and CC BY 4.0 notice.
- `items.json`, `assignment_a.json`, `assignment_b.json`: deterministic blind schema inputs for coordinator tools.
- `manifest.json`: source hashes, attribution, selection counts, kit/UI/guide revision, artifact hashes, and pending-review status. Coordinator material only.
- `build_kit.py`: portable deterministic builder and byte-exact `--check-only` verifier.
- `tests/test_arabic_annotation.py`: synthetic schema-only tests, not annotations.

Do not give reviewers the other assignment's HTML, the raw source sidecar, prior AI-review material, semantic notes, source/proxy labels, quarantine decisions, or coordinator manifest. Each distributed HTML contains one assignment and no case/condition/split membership or model outputs.

## Mandatory pre-distribution verification

On a fresh checkout, point to the external read-only raw directory explicitly and run `--check-only` **before distributing either HTML**. This verifies every generated artifact byte-for-byte and writes nothing:

```bash
python3 -I -B arabic_annotation/build_kit.py \
  --raw-root /path/to/read-only/issue8_arabic \
  --check-only
```

Alternatively, use the environment variable:

```bash
export EVTUNE_ARABIC_RAW_ROOT=/path/to/read-only/issue8_arabic
python3 -I -B arabic_annotation/build_kit.py --check-only
```

Proceed only when the command exits successfully and prints `Verified 20 blind Arabic rows`. Record the reported kit revision. Distribution without this check is not permitted.

## Two isolated independent reviewers

1. Assign **A** and **B** to two different, qualified native-Arabic human reviewers. Verify language qualification and task competence independently; software cannot prove either.
2. After the mandatory check, give `annotate_a.html` only to A and `annotate_b.html` only to B, with the guide.
3. **Require separate devices or isolated browser profiles.** A reviewer must not open the other HTML, browser profile, local storage, drafts, or exports. Local-storage keys include both assignment ID and kit revision; imports also reject the other assignment and mismatched revisions.
4. Require independent work: no AI-generated judgments, external evidence searches, hidden labels, stored model outputs, or consultation between reviewers. Uncertainty and disagreement are valid.
5. Reviewers judge the strict claim/evidence relation and citation under contract v2. Every row also requires five Arabic assessments: naturalness, register/dialect, concatenation/noise, figurative language, and possible translation. The UI encodes them in `notes` as `ARABIC_LANGUAGE_REVIEW_V1`; the shared semantic schema is unchanged.
6. Keep source text, drafts, complete exports, identities, and coordinator outputs private and evaluation-only. Do not upload them to public services or use them for training, prompting, model selection, or case-level publication.

## Drafts, completion, revision binding, and attestation

Draft export is for backup/resume only. It always uses:

```json
{
  "submission_status": "draft",
  "annotation_origin": "human_draft",
  "synthetic": false,
  "human_attestation": false
}
```

Complete export requires all 20 rows, valid cross-field relationships, all five language assessments, and explicit human attestation. Only then does it use `submission_status: complete`, `annotation_origin: human_attested`, and `human_attestation: true`. Exports carry `kit_revision`, a hash binding the builder, shared validation library, guide, and UI. Complete import runs the same per-row consistency checks and rejects contradictory attested files, missing language review, wrong assignments, and wrong revisions.

Preserve both original exports separately. Arabic exports must carry a `kit_revision`; agreement and adjudication additionally require the coordinator to supply the expected revision read from the verified manifest. Equal but arbitrary revisions on A and B are not sufficient. Tools reject drafts, unattested or synthetic exports by default, invalid language assessments, missing revisions, and mismatch with the manifest-approved value. Adjudication decisions must retain that same revision.

No synthetic fixture may be described as human or native annotation. Tests use in-memory synthetic rows solely to exercise schema compatibility; derived test reports remain marked `SYNTHETIC_TEST_NOT_HUMAN`.

## Agreement and adjudication

Run from the project root after receiving the two actual complete exports. Read the expected revision from the verified coordinator manifest, never from either export:

```bash
KIT_REVISION=$(python3 -c 'import json; print(json.load(open("arabic_annotation/manifest.json", encoding="utf-8"))["kit_revision"])')
```

Existing output writers are confined to `annotation/`, so keep coordinator results there and keep this kit unchanged.

```bash
mkdir -p annotation/arabic_native_results
python3 -I annotation/agreement.py \
  --items arabic_annotation/items.json \
  --assignment-a arabic_annotation/assignment_a.json \
  --assignment-b arabic_annotation/assignment_b.json \
  --expected-kit-revision "$KIT_REVISION" \
  --a /private/path/arabic-annotator-a-complete.json \
  --b /private/path/arabic-annotator-b-complete.json \
  --output annotation/arabic_native_results/agreement.json
```

Prepare the conflict-only queue and blank decision worksheet:

```bash
python3 -I annotation/adjudicate.py prepare \
  --items arabic_annotation/items.json \
  --assignment-a arabic_annotation/assignment_a.json \
  --assignment-b arabic_annotation/assignment_b.json \
  --expected-kit-revision "$KIT_REVISION" \
  --a /private/path/arabic-annotator-a-complete.json \
  --b /private/path/arabic-annotator-b-complete.json \
  --output annotation/arabic_native_results/adjudication_queue.json \
  --template-output annotation/arabic_native_results/adjudication_decisions.json
```

A qualified human adjudicator reviews conflicts under the same guide, fills every blank annotation and rationale, completes language assessment for adjudicated rows, sets a real adjudicator ID, and adds their human attestation only after completion. Then merge:

```bash
python3 -I annotation/adjudicate.py merge \
  --items arabic_annotation/items.json \
  --assignment-a arabic_annotation/assignment_a.json \
  --assignment-b arabic_annotation/assignment_b.json \
  --expected-kit-revision "$KIT_REVISION" \
  --a /private/path/arabic-annotator-a-complete.json \
  --b /private/path/arabic-annotator-b-complete.json \
  --decisions annotation/arabic_native_results/adjudication_decisions.json \
  --output annotation/arabic_native_results/merged_annotations.json
```

Agreement measures consistency, not correctness. All five derived Arabic assessment values have their own agreement metrics, and any difference enters the adjudication queue even when the semantic fields agree. Preserve the two original exports, agreement report, conflict queue, decisions, and merged output as a private audit trail. Any downstream evaluation remains a separate, later step.

## Rebuild and test

From the project root, with `EVTUNE_ARABIC_RAW_ROOT` set as above:

```bash
python3 -I -B arabic_annotation/build_kit.py --check-only
python3 -I -B -m unittest discover -s arabic_annotation/tests -v
```

To regenerate intentionally, use `--overwrite`. Every output is first written and verified as LF-exact bytes in a staging directory; replacement begins only after all staged writes succeed. Every original artifact is backed up before replacement, and a replacement-phase failure rolls all outputs back byte-for-byte. Outputs are confined to `arabic_annotation/`; raw input/output collisions are rejected. No network, model, paid job, or MPS path is used.
