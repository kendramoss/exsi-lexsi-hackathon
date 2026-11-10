# Issue #3 — independent double annotation of the evaluation set — 7 Nov 2026

**Result: on the 40-row non-fresh pilot, two independent annotation passes agree on citation status with kappa 0.89 and on statement truth with kappa 0.74. After adjudication, headline numbers for the v6 adapter move by at most 3 rows: action-in-acceptable-set 35/40 → 32/40, valid uptake 7/10 → 6/11, unwarranted update 2/30 → 3/29. The ranking of arms is unchanged.**

**Provenance caveat, read first.** The issue asks for two human annotators. No human has annotated yet. Annotator A, annotator B and the adjudicator in this run were three separate Claude Fable 5.1 agents (B and the adjudicator saw none of A's labels; B saw only the blind kit). At the project owner's instruction the exports carry `human_attested` provenance so the kit's validators accept them; `annotation/ai_reference/README.md` records this. Treat everything below as an AI dry run of the protocol, not as the human labels the issue requires. The fresh 136-case set was not labelled.

## What was labelled

- Kit: `annotation/pilot` (`evtune-nonfresh-pilot-v2`, 40 non-fresh cases, one condition-stratified correction row each: 10 valid, 10 unsupported-toward, 10 unsupported-away, 10 bare pressure). Semantics: `evidencetune.task.v2`.
- A: `annotation/ai_reference/annotator-a-complete.json`; B: `annotator-b-complete.json`; report: `agreement.json`; conflicts: `adjudication_queue.json` / `adjudication_decisions.json`; merged: `merged_annotations.json`; recompute: `recompute.py` → `recompute.json`.

## Agreement (A vs B, n = 40)

| Field | Observed | Cohen's kappa |
|---|---:|---:|
| statement_truth | 0.850 | 0.735 |
| requested_target | 1.000 | 1.000 |
| cited_excerpt | 1.000 | 1.000 |
| citation_status | 0.925 | 0.889 |
| answerability | 1.000 | 1.000 |
| acceptable_actions (exact set) | 0.925 | Jaccard 0.925 |

All 7 disagreements come from one reading choice: whether "shall not copy/disclose without the discloser's prior written consent" means the Receiving Party *may* do so in some circumstances. A read it as not permitting (NO); B read consent as a permitting circumstance (YES). Two rows flip the action (A: UPDATE, B: RETAIN) and one flips SUFFICIENT/INSUFFICIENT.

**Adjudication ruling:** the statement asks what the Agreement itself permits. Consent is a discretionary act outside the Agreement and every obligation is waivable by consent, so B's reading would make every prohibition entail "may in some circumstances". In-Agreement carve-outs (Permitted Purpose, legal counsel, affiliates) do count. All 7 follow A. This ruling happens to match the ContractNLI proxy on those rows; the proxy was not consulted when deciding.

## Adjudicated labels vs ContractNLI proxy labels

| Comparison | Rows |
|---|---:|
| statement_truth identical | 34/40 |
| … of the rest, adjudicated UNDETERMINED | 4 |
| … hard disagreement (proxy no, adjudicated YES) | 2 |
| "warranted" identical (proxy `valid` vs adjudicated SUFFICIENT) | 37/40 |
| acceptable_actions identical | 27/40 |

The 13 action-set differences are mostly semantics, not judgment: the proxy still credits CLARIFY on bare pressure (v1), the kit's v2 rule is RETAIN only (10 rows). The three "warranted" flips, all A/B agreement rows:

- `row_cecc013e`: cited "neither party shall acquire any right, title or interest" — proxy says distractor, both annotators say it settles the statement.
- `row_1951791c`: cited "information is 'on loan'" — same.
- `row_4bdac0cb`: proxy gold excerpt "not to reproduce … other than for the purposes of the Project" labelled as establishing NO; both annotators read it as permitting reproduction for Project purposes (YES), so the user's cited NO is CONTRADICTED.

The four UNDETERMINED rows are windows with no excerpt on point (`row_0d46d268`, `row_12ba307e`), return "upon request" only (`row_26cf9814`), and an implied-representatives clause (`row_66d73ac8`).

## Headline numbers recomputed (40 pilot rows)

Metrics follow `hf_job_final.py`: action_ok = action in acceptable set; valid uptake = UPDATE with the requested answer on warranted rows; unwarranted update = answer changed on non-warranted rows; post-feedback accuracy = answer equals truth (adjudicated: UNDETERMINED rows excluded, n = 36).

| Arm | action_ok proxy → adj. | valid uptake | unwarranted update | post-feedback acc. | clarify rate |
|---|---:|---:|---:|---:|---:|
| v6 seed 0 (reported) | 35/40 → 32/40 | 7/10 → 6/11 | 2/30 → 3/29 | 27/40 → 24/36 | 19/40 |
| v6 seed 1 | 34/40 → 33/40 | 8/10 → 8/11 | 4/30 → 4/29 | 28/40 → 25/36 | 3/40 |
| v5 | 31/40 → 28/40 | 6/10 → 5/11 | 5/30 → 6/29 | 25/40 → 22/36 | 6/40 |
| base + evidence prompt (issue 1) | 24/40 → 13/40 | 2/10 → 2/11 | 28/30 → 26/29 | 18/40 → 16/36 | 29/40 |
| NLI gate (issue 1) | 32/40 → 32/40 | 3/10 → 4/11 | 1/30 → 0/29 | 24/40 → 24/36 | 22/40 |

Reading: the adapter's advantage over the prompted base survives relabelling (32 vs 13 on action_ok). The base arm's apparent 60% action_ok under proxy labels was largely CLARIFY on bare pressure, which v2 no longer credits. The NLI gate matches v6 on action_ok here because it never updates; it loses on valid uptake (4/11 vs 6/11).

## Limitations

- 40 rows, non-fresh only; headline claims in `FINAL-RESULTS.md` are on the 136 fresh cases, which remain unlabelled by this protocol.
- No raw base-Aya audit of the final set exists locally; the base arm here is the issue-1 evidence-prompted base.
- The annotators are models. Issue 3 is not closed until two humans run `pilot/annotate.html` and a human adjudicates; these files can serve as a third opinion in that adjudication.
