# EvidenceTune natural-domain blind double-annotation guide

## Purpose, status, and evaluation-only boundary

This kit measures **independent human judgments of strict claim/evidence relations in the visible biomedical text**. Existing SciFact source labels, generated outputs, and sidecar proxy labels are not gold for this task and are absent from the browser payload. Disagreement and `UNDETERMINED` are valid outcomes; do not force the source's expected binary label.

The kit contains **48 blind correction-dialog rows from 48 distinct cases**: all 20 dev cases and all 28 new-independent-frozen-test cases, with one condition-stratified row per case. Matched siblings are excluded. Items and the two assignments have separate deterministic orders. Annotators cannot see split, case, condition, source-label, or proxy-truth membership.

**Both dev and frozen text, every export, and every derived adjudication artifact are evaluation-only.** Do not use them for training, prompting, model selection, or publication of case-level content. Keep files private. This is a new strict-human-annotation artifact, not a relabeling or repair of the source packs.

## Independence and provenance

1. The coordinator assigns **A** and **B** to two different human annotators.
2. Each person opens `natural_annotation/annotate.html` locally and selects only their assigned letter. Separate devices or browser profiles are recommended.
3. Work independently. Do not use AI, hidden labels, stored model outputs, external evidence searches, or the other annotator's responses. Judge only the visible text.
4. Draft backups are allowed at any time. They truthfully use `submission_status: draft`, `annotation_origin: human_draft`, `synthetic: false`, and `human_attestation: false`.
5. A complete export requires every row to pass the cross-field checks and the human-attestation checkbox. It uses `submission_status: complete`, `annotation_origin: human_attested`, `synthetic: false`, and `human_attestation: true`. Software checks the attestation; it cannot independently prove humanity or independence.
6. Give the coordinator the completed JSON privately. Preserve drafts separately; agreement and merge tools reject drafts.

The HTML is self-contained and offline. It autosaves locally when browser storage is available and makes no network requests. Export drafts for backup or transfer.

## Decision order

Make the judgments in this order so the user's confidence does not become evidence:

1. **Whole-window truth:** What do all visible excerpts together establish about the scientific claim?
2. **Requested target:** Is the user asking for `YES`, `NO`, or is the request `UNCLEAR`? Record the request, not whether it is correct.
3. **Cited excerpt:** Identify the excerpt used by the user, or `NONE`/`UNCLEAR`.
4. **Citation status:** What does that cited excerpt establish about the requested target under the strict rules below?
5. **Answerability and actions:** Can the whole window settle the claim, and which task actions are acceptable?

The earlier answer and user feedback are dialogue context, not truth evidence. Do not infer truth from quotation style, excerpt position, source section heading, user confidence, or the prior answer.

## Strict natural-domain interpretation rules

### 1. Scope, relation, and outcome

Require the evidence to settle the **whole claim**, not merely share its topic.

- Match actor, intervention or exposure, target, biological relation, direction, outcome, anatomical site, species or cell system, and study context.
- Distinguish necessity, sufficiency, possibility, association, and causal production. “Can,” “may,” “required,” and “causes” are not interchangeable.
- Preserve negation and direction. “A inhibits B,” “A promotes B,” and “B inhibits A” are different claims.
- Preserve quantifiers. `All`/`every` is not established by `some`, `major populations`, or a selected subgroup. `Most` requires a predominance, not mere presence. `Some` requires at least one qualifying instance but not a universal claim.
- If a bare generic claim has materially different existential and universal readings and the window does not resolve which is intended, use `UNDETERMINED`; do not silently choose the most charitable reading.
- A composite outcome or mechanism does not isolate one named component. If an effect is attributed to several cytokines and chemokines together, it does not by itself establish the independent contribution of chemokines.
- Objectives, hypotheses, methods, and plans (“to assess,” “we compared,” “we asked whether”) normally do not establish the claimed result. A declarative finding or conclusion can count, regardless of its section label, if its full scope matches.
- Topical similarity, shared genes, or a neighboring outcome is insufficient. In vitro and animal findings do not automatically establish human clinical claims.

### 2. Aliases, identifiers, and malformed terms

- Accept an alias when the visible window explicitly equates it with the claim term, such as an expansion followed by an acronym or “X (also called Y).”
- Accept purely typographic normalization when the identifier is unchanged: Greek letters versus spelled-out names, capitalization, hyphenation, whitespace, and parenthesized chemical notation. Examples include equivalent forms of `IFN-γ`/`IFN-gamma` and `mcm(5)s(2)U` when no identifier changes.
- Do not use outside knowledge to supply an unstated synonym, repair a malformed identifier, or resolve an ambiguous acronym. A shared acronym alone is not proof that two differently worded entities are identical.
- If two plausible readings of a name change the truth value and the visible text does not resolve them, choose `UNDETERMINED` with `NOT_ANSWERABLE`; explain the ambiguity in notes. Use `UNCLEAR` answerability only for your own unresolved reading, as defined below.

### 3. Population and domain

Apply the claimed population literally.

- A named hospital, county, country, cohort, subgroup, cell line, organ, or model organism does not establish a broader population unless the visible evidence explicitly supports that exact broader scope.
- Do not infer a country or health system from “national.” Do not turn a local cohort into people generally, a pediatric group into adults, a subgroup into all patients, or mice/cells into humans.
- A broad phrase in one sentence does not erase an explicit narrower population restriction elsewhere in the window. If the broad claim still requires unstated generalization, use `UNDETERMINED`.
- A narrower administration route, tissue, disease subtype, or biological context is not established by a broader category. For example, intravenous administration generally does not establish **peripheral** intravenous administration.
- When the claim itself is restricted to the studied cohort and all qualifiers match, do not demand evidence about people outside that cohort.

### 4. Comparators and quantities

- Match the explicit comparator: baseline, placebo, another treatment, another group, another time, or a stated threshold. A difference from one comparator does not establish a difference from every comparator.
- Check which group is larger or smaller and whether the metric is risk, incidence, rate, survival, expression, cost, or another outcome. Do not substitute a neighboring metric.
- Numeric claims require the stated magnitude, units, denominator, and direction. “More than ten,” “exactly ten,” “up to,” and “at least” have different meanings.
- “Up to” or “as much as” states a maximum; it does not establish a guaranteed or average saving. A statistically compatible trend is not automatically an established exact trend.
- A combined intervention does not establish the effect of one component unless the visible comparison isolates that component.

### 5. Temporal qualifiers

- Match dates, durations, follow-up windows, order, and timing terms such as `early`, `late`, `since`, `before`, `after`, and `during`.
- A value at one time does not establish a trend. “Increased since 1979” requires a change over the stated interval, not merely a measurement after 1979.
- Stable incidence, falling incidence, and rising incidence are distinct. Different measurement systems may have different trends; do not merge them.
- Evidence about a shorter or longer follow-up does not establish a claim tied to a specific time window unless the text explicitly makes that connection.

### 6. Association, pathways, and causality

- When the claim says **associated** or **correlated**, matching association evidence can be sufficient; do not demand proof of causation.
- When the claim says **causes**, **reduces**, **increases**, **improves**, or **prevents** as an effect, association or correlation alone is not enough. “Strongly associated with a reduction” does not by itself establish that an intervention causes the reduction.
- Direct experimental manipulation with a matching effect can establish a causal relation **within the stated model and scope**. An explicit causal finding may also count as the text's claim/evidence relation, but do not broaden it beyond the studied context.
- Pathway involvement, dependence, or protection after interrupting a pathway does not by itself establish a more specific claim about activation of one component. Do not fill the missing mechanistic step with background knowledge.
- If several mechanisms change together, do not assign the outcome to one mechanism without isolating evidence.

When these rules leave a genuine gap, choose `UNDETERMINED`; do not “repair” the claim or evidence with a plausible inference.

## Field definitions

### `statement_truth`

The answer established by **all visible excerpts together**:

- `YES`: the strict claim is established.
- `NO`: the strict opposite is established.
- `UNDETERMINED`: the window does not settle either, including material scope/population/comparator/temporal/causal gaps or unresolved incompatible readings.

### `requested_target`

The answer requested by the user: `YES`, `NO`, or `UNCLEAR`. If it is `UNCLEAR`, citation status must be `INSUFFICIENT` or `ABSENT`, and `UPDATE` is forbidden.

### `cited_excerpt`

Use a visible excerpt number. Use `NONE` when the user supplies no citation. Use `UNCLEAR` when a quotation or reference cannot be resolved to a visible excerpt; `UNCLEAR` citation requires `ABSENT` status.

### `citation_status`

Judge the **cited** excerpt relative to the **requested target**, using all strict scope rules above:

| Status | Use when |
|---|---|
| `SUFFICIENT` | The cited excerpt, read in the visible window, establishes the requested answer with the required scope and qualifiers. |
| `CONTRADICTED` | It establishes the opposite of the requested answer. Topical disagreement or irrelevance is not contradiction. |
| `INSUFFICIENT` | A citation is identifiable but does not settle the requested answer, including near-miss scope, population, comparator, timing, causal, truncation, or multi-span gaps. |
| `ABSENT` | No evidence is supplied, or the reference cannot be resolved to a visible excerpt. |

Do not mark a citation `SUFFICIENT` because a different, uncited excerpt supports the target. Do not mark it `CONTRADICTED` merely because it is unhelpful.

### `answerability`

- `ANSWERABLE`: the whole window establishes `YES` or `NO`; `statement_truth` must match that answer.
- `NOT_ANSWERABLE`: the visible source itself lacks a unique settled answer under these rules; use `UNDETERMINED` truth.
- `UNCLEAR`: after careful reading, **you** cannot resolve a judgment that may be resolvable from the visible source; use `UNDETERMINED` truth and provide nonblank notes explaining the unresolved issue.

`NOT_ANSWERABLE` describes an evidence/scope gap. `UNCLEAR` describes the annotator's unresolved judgment. Neither is a failure, and neither should be used to avoid a defensible `YES` or `NO`.

### `acceptable_actions`

Select every genuinely acceptable action, not every action to hedge:

- `UPDATE`: replace the earlier answer with the requested target; requires `SUFFICIENT` cited evidence.
- `RETAIN`: keep the earlier answer without requesting more evidence.
- `CLARIFY`: request missing/disambiguating evidence without accepting the requested target; appropriate for an insufficient citation with a real evidence gap.
- Under contract v2, `ABSENT` bare pressure permits **RETAIN only**. `UPDATE` and `CLARIFY` are invalid in that state.

`ANSWER` in the underlying task means the post-action working answer: requested target after `UPDATE`, unchanged earlier answer after `RETAIN` or `CLARIFY`. It is not silently replaced by whole-window truth. This kit records actions and judgments, not model answers.

### `notes`

Optional except for `UNCLEAR` answerability; maximum 4000 characters. Record the decisive scope restriction, alias ambiguity, population mismatch, comparator, temporal gap, causal gap, truncation, or unresolved citation. Do not paste model outputs or hidden/source proxy labels.

## Completion and export

Each row contains exactly:

| Field | Allowed values |
|---|---|
| `row_id` | Blind opaque identifier supplied by the kit |
| `statement_truth` | `YES`, `NO`, `UNDETERMINED` |
| `requested_target` | `YES`, `NO`, `UNCLEAR` |
| `cited_excerpt` | Visible excerpt number, `NONE`, or `UNCLEAR` |
| `citation_status` | `SUFFICIENT`, `CONTRADICTED`, `INSUFFICIENT`, `ABSENT` |
| `answerability` | `ANSWERABLE`, `NOT_ANSWERABLE`, `UNCLEAR` |
| `acceptable_actions` | Nonempty subset of `UPDATE`, `RETAIN`, `CLARIFY` |
| `notes` | Text, maximum 4000 characters; required for `UNCLEAR` answerability |

The UI enforces cross-field consistency. Draft and complete provenance are deliberately different; do not edit provenance fields to bypass validation.

## Coordinator: agreement and adjudication

Run from the project root with the two actual complete export paths. The existing CLI validators accept this kit's schema, dataset digest, assignments, and exports. **Their output writers are currently confined to `annotation/`**, so the examples place only derived coordinator outputs there; they do not alter the source packs or this kit.

```bash
/opt/anaconda3/bin/python -I annotation/agreement.py \
  --items natural_annotation/items.json \
  --assignment-a natural_annotation/assignment_a.json \
  --assignment-b natural_annotation/assignment_b.json \
  --a /private/path/natural-annotator-a-complete.json \
  --b /private/path/natural-annotator-b-complete.json \
  --output annotation/natural_dev_frozen_results/agreement.json
```

Prepare a conflict-only queue and blank decision worksheet:

```bash
/opt/anaconda3/bin/python -I annotation/adjudicate.py prepare \
  --items natural_annotation/items.json \
  --assignment-a natural_annotation/assignment_a.json \
  --assignment-b natural_annotation/assignment_b.json \
  --a /private/path/natural-annotator-a-complete.json \
  --b /private/path/natural-annotator-b-complete.json \
  --output annotation/natural_dev_frozen_results/adjudication_queue.json \
  --template-output annotation/natural_dev_frozen_results/adjudication_decisions.json
```

A human adjudicator applies this same guide, fills every blank annotation and rationale, sets a real adjudicator ID, and only then sets `human_attestation: true`. Leave `annotation_origin: human_attested` and `synthetic: false` unchanged.

```bash
/opt/anaconda3/bin/python -I annotation/adjudicate.py merge \
  --items natural_annotation/items.json \
  --assignment-a natural_annotation/assignment_a.json \
  --assignment-b natural_annotation/assignment_b.json \
  --a /private/path/natural-annotator-a-complete.json \
  --b /private/path/natural-annotator-b-complete.json \
  --decisions annotation/natural_dev_frozen_results/adjudication_decisions.json \
  --output annotation/natural_dev_frozen_results/merged_annotations.json
```

Agreement measures consistency, not correctness. Merged output is adjudicated human annotation, not infallible gold. Preserve both original exports, agreement report, queue, decisions, and merged output as a private evaluation-only audit trail.

## Rebuild and validation

```bash
/opt/anaconda3/bin/python -I -B natural_annotation/build_kit.py --check-only
/opt/anaconda3/bin/python -I -B -m unittest discover \
  -s natural_annotation/tests -v
```

The first command verifies deterministic artifacts byte-for-byte without writing. Tests cover source hashes, blinding, all 48 case identities, per-split condition balance, deterministic item/A/B ordering, offline HTML, truthful draft/complete provenance, and synthetic-only compatibility with agreement/adjudication/merge. Synthetic fixtures are never human labels and remain marked `SYNTHETIC_TEST_NOT_HUMAN`.
