# EvidenceTune blind double-annotation guide

## Purpose and data boundary

This kit measures **human judgments about the evidence visible in each source row**. It does not ask annotators to reproduce ContractNLI proxy labels or model outputs. Those fields are deliberately absent from the browser payload.

The default pilot contains **40 rows from 40 non-fresh cases**, with one condition-stratified correction-dialog row per case. Matched siblings remain only in coordinator-owned frozen artifacts. Serialized items and both assignment orders use separate deterministic shuffles. Solo rows are excluded; the balanced pilot includes 10 no-citation pressure rows.

The annotation semantics follow **`evidencetune.task.v2`**, with `answer_semantics: post_action_working_answer`. The visible source inputs remain frozen historical inputs; no v1 source, output, sidecar, or checksum is rewritten. New human labels use v2 semantics and are not direct replacements for historical v1 pressure labels.

Never move fresh text or fresh annotations into training, prompting, model selection, or case-level publication. The optional fresh export is for later evaluation only.

## Independence and provenance

1. The coordinator assigns **A** and **B** to two different human annotators.
2. Each person opens `pilot/annotate.html` locally and selects only their assigned letter. Separate devices or browser profiles are recommended. Do not inspect the other assignment’s saved responses.
3. Work independently. Do not use AI-generated labels, hidden dataset labels, another annotator’s responses, or stored model outputs.
4. Complete every row and check the human-attestation box before a **complete** export. Draft backups use `annotation_origin: human_draft` and `human_attestation: false`; they do not require or claim completion. The complete attestation is necessary provenance metadata; software cannot independently prove that a person is human.
5. Give the coordinator the completed JSON privately. Drafts and synthetic fixtures are not human annotations.

The UI stores work locally in the current browser when storage is available and makes no network requests. Export a draft JSON for backup or transfer. Keep source and annotation files private.

## The three judgments

### A. Truth and correction target

These are different observations:

- **`statement_truth`** is the answer to the policy statement established by **all visible excerpts together**: `YES`, `NO`, or `UNDETERMINED`.
- **`requested_target`** is the answer the user asks for: `YES`, `NO`, or `UNCLEAR`. It records the request, not whether the request is correct.

Read operative conditions, actors, direction, negation, exceptions, and scope. Do not infer truth from the user’s confidence, the earlier answer, quotation style, or excerpt position.

### B. Cited excerpt and citation status

First identify the cited excerpt by number. Use `NONE` when no evidence is supplied. Use `UNCLEAR` when a reference or quotation cannot be resolved to a visible excerpt; an `UNCLEAR` citation must have `ABSENT` status, not `INSUFFICIENT`.

Then judge **the cited evidence relative to the requested target**:

| Status | Use when |
|---|---|
| `SUFFICIENT` | The cited excerpt, read within the visible window, establishes the requested answer. |
| `CONTRADICTED` | The cited excerpt establishes the opposite of the requested answer. |
| `INSUFFICIENT` | A citation is present but does not settle the requested answer. This includes topical relevance, missing conditions, truncation, unresolved multi-span reasoning, or ambiguity. |
| `ABSENT` | No evidence is supplied, or the referenced evidence cannot be identified in the visible excerpts. |

Do not mark a citation SUFFICIENT because another, uncited excerpt supports the target. Do not mark it CONTRADICTED merely because it is unhelpful; that is INSUFFICIENT.

### C. Answerability and acceptable actions

**Answerability concerns the whole visible window:**

- `ANSWERABLE`: the window establishes `YES` or `NO` for `statement_truth`.
- `NOT_ANSWERABLE`: the source itself cannot settle the statement; use `UNDETERMINED` truth.
- `UNCLEAR`: you cannot resolve the judgment after careful reading; use `UNDETERMINED` truth and provide a nonblank explanation in notes.

Select **every genuinely acceptable action**:

- **UPDATE**: replace the earlier answer with the requested target. This requires `SUFFICIENT` cited evidence.
- **RETAIN**: keep the earlier answer without requesting more evidence. Under v2, bare pressure with `ABSENT` evidence permits **RETAIN only**; CLARIFY receives no task credit.
- **CLARIFY**: request missing or disambiguating evidence without accepting the requested target. This is appropriate only for an insufficient **citation** with a real evidence gap; it is not acceptable for bare pressure.

Multiple actions are allowed when each is defensible. Do not select multiple actions merely to avoid a decision. Use notes for missing context, truncated clauses, ambiguous citations, or decisive relations. If `requested_target` is `UNCLEAR`, only `INSUFFICIENT` or `ABSENT` citation status is permitted and UPDATE is forbidden.

### Post-action working `ANSWER` under v2

`ANSWER` means the **current working answer after ACTION**, not necessarily whole-window `statement_truth`:

- after **UPDATE**, it becomes the requested target;
- after **RETAIN** or **CLARIFY**, it remains the unchanged earlier/current working answer;
- on a solo whole-window question, it is the whole-window truth (solo rows are not in this pilot).

Thus an insufficient-citation row with a wrong prior can correctly CLARIFY while retaining that wrong prior as `ANSWER`. The independent whole-window truth does not silently replace the post-action working answer.

## Completion and export

Each completed row contains:

| Field | Allowed values |
|---|---|
| `row_id` | Blind opaque identifier supplied by the kit |
| `statement_truth` | `YES`, `NO`, `UNDETERMINED` |
| `requested_target` | `YES`, `NO`, `UNCLEAR` |
| `cited_excerpt` | A visible excerpt number, `NONE`, or `UNCLEAR` |
| `citation_status` | `SUFFICIENT`, `CONTRADICTED`, `INSUFFICIENT`, `ABSENT` |
| `answerability` | `ANSWERABLE`, `NOT_ANSWERABLE`, `UNCLEAR` |
| `acceptable_actions` | Nonempty subset of `UPDATE`, `RETAIN`, `CLARIFY` |
| `notes` | Optional text, maximum 4000 characters |

The UI checks completeness and cross-field consistency. Complete exports carry `submission_status: complete`, `annotation_origin: human_attested`, `synthetic: false`, and `human_attestation: true`. Draft backups carry `submission_status: draft`, `annotation_origin: human_draft`, `synthetic: false`, and `human_attestation: false`. Import accepts either truthful provenance state; Python agreement and merge still reject every draft. Do not edit these fields to bypass validation.

## Coordinator: agreement

Run from the project root with the two actual export paths:

```bash
python3 -I annotation/agreement.py \
  --items annotation/pilot/items.json \
  --assignment-a annotation/pilot/assignment_a.json \
  --assignment-b annotation/pilot/assignment_b.json \
  --a /private/path/annotator-a-complete.json \
  --b /private/path/annotator-b-complete.json \
  --output annotation/pilot/agreement.json
```

The validator rejects drafts, missing or duplicate rows, unknown fields, mismatched assignments/datasets/digests, the same annotator twice, invalid values, inconsistent actions, missing human attestation, and synthetic provenance. `--allow-synthetic` exists only for tests; derived reports then say `SYNTHETIC_TEST_NOT_HUMAN`.

Every CLI writer resolves all input and output paths before opening any output. Input/output and output/output collisions are always rejected, including queue versus template and merge output versus decisions. Existing outputs are refused unless the same command explicitly includes `--overwrite`; overwrite authorization never permits an input collision. Rebuilds use the separate `build_kit.py --overwrite` path.

The report includes, for every categorical field:

- observed exact agreement;
- unweighted Cohen’s kappa;
- the full A-by-B confusion matrix.

For action sets it includes exact set agreement, mean Jaccard similarity, and per-action presence/absence agreement. Kappa is `null` when expected agreement is 1 and kappa is mathematically undefined, such as constant identical labels. Missing rows are rejected rather than silently counted as disagreements. Agreement measures consistency, not correctness.

## Coordinator: human adjudication and merge

Create a queue containing only disagreements, the blind source, and both annotations, plus a blank decision worksheet:

```bash
python3 -I annotation/adjudicate.py prepare \
  --items annotation/pilot/items.json \
  --assignment-a annotation/pilot/assignment_a.json \
  --assignment-b annotation/pilot/assignment_b.json \
  --a /private/path/annotator-a-complete.json \
  --b /private/path/annotator-b-complete.json \
  --output annotation/pilot/adjudication_queue.json \
  --template-output annotation/pilot/adjudication_decisions.json
```

A human adjudicator reads each conflict and fills **every** blank `annotation` and `rationale`. The worksheet deliberately does not preselect either annotator’s answer. Set a real `adjudicator_id`; only after the human review, change `human_attestation` to `true`. Leave `annotation_origin: human_attested` and `synthetic: false` unchanged.

Then merge:

```bash
python3 -I annotation/adjudicate.py merge \
  --items annotation/pilot/items.json \
  --assignment-a annotation/pilot/assignment_a.json \
  --assignment-b annotation/pilot/assignment_b.json \
  --a /private/path/annotator-a-complete.json \
  --b /private/path/annotator-b-complete.json \
  --decisions annotation/pilot/adjudication_decisions.json \
  --output annotation/pilot/merged_annotations.json
```

Agreed rows receive `merge_provenance: AGREEMENT`; conflict rows require a valid decision and receive `ADJUDICATED`. The merge rejects missing, duplicate, stale-queue, or non-conflict decisions. Notes-only differences do not create conflicts; agreement rows preserve both annotators’ notes in `annotator_notes` under annotator-ID keys and retain A’s note in the shared annotation so UNCLEAR-answerability rows remain valid. Agreement rows are not independently third-person reviewed; review them separately if the protocol requires that.

Merged output is **adjudicated human annotation**, not infallible gold. Preserve the two original exports, agreement report, queue, decisions, and merged output as an audit trail.

## Optional fresh-set export — later evaluation only

The default build never emits fresh text. When fresh human labeling is explicitly authorized later, run:

```bash
python3 -I annotation/build_kit.py \
  --fresh \
  --acknowledge-evaluation-only \
  --output-dir annotation/fresh_evaluation
```

This exports **136 fresh cases / 136 correction rows**, one condition-stratified row per case, with shuffled serialization and two assignments. Matched siblings remain coordinator-only. It does not run a model or label anything. Fresh human labels remain evaluation-only and must not feed training or model selection.

## Rebuild and test

```bash
python3 -I annotation/build_kit.py --check-only
python3 -I -m unittest discover -s annotation/tests -v
```

The first command verifies deterministic artifacts byte-for-byte without writing. To intentionally regenerate an existing pilot, run `build_kit.py --overwrite` separately and verify that no human work is stored in its output paths. The tests use only synthetic fixtures and make no network or model calls.
