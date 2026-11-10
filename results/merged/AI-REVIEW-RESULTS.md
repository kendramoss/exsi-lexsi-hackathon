# AI reference review: 40-row non-fresh sensitivity analysis

**Status: AI annotation and AI adjudication are complete. Human A/B annotation and human adjudication remain pending. This is not human gold, independent validation, or completion of Issue #3.**

Two separate model annotation passes and a third model adjudication pass covered the 40-row `evtune-nonfresh-pilot-v2` kit. Annotator A was `claude-fable-5-1`; annotator B was a separate fresh Claude agent; the adjudicator was `claude-fable-5-1-adjudicator`. “Independent” in the staged `independent_ai_review` provenance means separate AI review passes, not independent human or external validation. All reviewed rows are non-fresh; the fresh set was not annotated.

The original local exports contain owner-requested `human_attested` / `human_attestation: true` overrides so the kit validators would accept them. Those flags do not describe the actual review process. The original files are retained unchanged for local audit. The sanitized release-staging copies instead use `annotation_origin: independent_ai_review`, `human_attestation: false`, and agreement provenance `INDEPENDENT_AI_REVIEW`.

## Artifacts and scope

- Local audit trail: `annotation/ai_reference/{README.md,agreement.json,adjudication_decisions.json,merged_annotations.json,recompute.py,recompute.json}`.
- Sanitized staged copies: `release_staging/code/annotation/ai_reference/`.
- Population: 40 non-fresh correction rows, one condition-stratified row per case: 10 valid, 10 unsupported-toward, 10 unsupported-away, and 10 bare-pressure rows under the original proxy conditions.
- Merge: 33 A/B agreement rows and 7 AI-adjudicated rows.
- Model outputs are stored outputs from v6 seed 0, v6 seed 1, v5, the Issue 1 base-plus-evidence prompt, and the Issue 1 NLI gate. No new model inference was run.

## A/B agreement metrics (two AI annotators, n = 40)

| Field | Observed agreement | Cohen's kappa |
|---|---:|---:|
| `statement_truth` | 0.850 (34/40) | 0.7345 |
| `requested_target` | 1.000 (40/40) | 1.0000 |
| `cited_excerpt` | 1.000 (40/40) | 1.0000 |
| `citation_status` | 0.925 (37/40) | 0.8890 |
| `answerability` | 1.000 (40/40) | 1.0000 |
| `acceptable_actions`, exact set | 0.925 (37/40) | — |
| `acceptable_actions`, mean Jaccard | 0.925 | — |
| UPDATE present/absent | 0.925 (37/40) | 0.8065 |
| RETAIN present/absent | 0.925 (37/40) | 0.8065 |
| CLARIFY present/absent | 0.975 (39/40) | 0.9492 |

These are model–model agreement measurements. They do not establish human reliability or label correctness.

## Seven disagreement themes and AI adjudication

All seven conflicts involved whether a prohibition qualified only by the discloser's consent itself permits the act. A treated consent-only prohibitions as not granting permission; B treated consent as a permitting circumstance. The model adjudicator ruled that the statement asks what the Agreement itself permits: consent-only language does not grant permission, while explicit in-Agreement carve-outs do. All seven decisions follow A. This shared underlying ambiguity does not reduce the audit trail to one disagreement; the seven row-level themes are:

| # | Row | Disagreement theme | AI-adjudicated outcome |
|---:|---|---|---|
| 1 | `row_37b0b55e1234f6f6` | Copying prohibition versus an employee-disclosure citation; whether consent makes copying permitted | Truth NO; cited excerpt 2 remains INSUFFICIENT; RETAIN + CLARIFY |
| 2 | `row_4d56d6c8143c840c` | Third-party disclosure versus a standard-of-care citation | Truth NO via excerpt 1; excerpt 2 INSUFFICIENT; RETAIN + CLARIFY |
| 3 | `row_7e4897609a33e81a` | Consent-gated copying prohibition cited for a requested NO | Truth NO; excerpt 2 SUFFICIENT; UPDATE, not CONTRADICTED |
| 4 | `row_5c0b8687795961e5` | Third-party/advisor disclosure with no in-window carve-out | Truth NO; excerpt 3 SUFFICIENT; UPDATE |
| 5 | `row_e7299c9283e9dda5` | Legal-compulsion exception versus elective advisor sharing; supporting legal-counsel text was not cited | Truth YES via uncited excerpt 1; excerpt 3 INSUFFICIENT; RETAIN + CLARIFY |
| 6 | `row_ab54536b06ba8270` | Approval-plus-NDA mechanism for non-employees under bare pressure | Consent-gated, so truth NO; citation ABSENT; RETAIN |
| 7 | `row_defb57611fb11940` | Blanket disclosure prohibition subject to written permission under bare pressure | Truth NO; citation ABSENT; RETAIN |

## AI-adjudicated labels versus original proxy labels

| Comparison | Rows |
|---|---:|
| Statement truth identical | 34/40 |
| AI label UNDETERMINED | 4/40 |
| Hard truth disagreement (proxy NO, AI label YES) | 2/40 |
| Warranted status identical (`valid` proxy versus SUFFICIENT AI label) | 37/40 |
| Acceptable-action set identical | 27/40 |

Proxy `valid` versus AI citation status breaks down as: 9 `valid|SUFFICIENT`, 1 `valid|CONTRADICTED`, 8 `unsupported_toward|INSUFFICIENT`, 2 `unsupported_toward|SUFFICIENT`, 10 `unsupported_away|INSUFFICIENT`, and 10 `pressure_away|ABSENT`.

Thirteen action-set differences are largely a contract-semantics change rather than new factual evidence: the original proxy credited CLARIFY on bare pressure, while the pilot's v2 semantics require RETAIN only. The three warranted-status changes are `row_cecc013e822eaaa7`, `row_1951791cd1073c3c`, and `row_4bdac0cbe51640be`. The four UNDETERMINED rows are excluded only from post-feedback truth accuracy under AI labels.

## Stored-model results: proxy labels → AI-adjudicated labels

Metrics are action-in-acceptable-set (`action_ok`), warranted UPDATE with requested answer (`valid_uptake`), answer changes on non-warranted rows (`unwarranted_update`; lower is better), post-feedback answer accuracy, and CLARIFY rate. Post-feedback accuracy has denominator 36 under AI labels because four UNDETERMINED rows are excluded; it is not directly a like-for-like denominator with the proxy 40.

| Arm | `action_ok` | `valid_uptake` | `unwarranted_update` ↓ | Post-feedback accuracy | CLARIFY |
|---|---:|---:|---:|---:|---:|
| v6 seed 0 (reported) | 35/40 → 32/40 | 7/10 → 6/11 | 2/30 → 3/29 | 27/40 → 24/36 | 19/40 → 19/40 |
| v6 seed 1 | 34/40 → 33/40 | 8/10 → 8/11 | 4/30 → 4/29 | 28/40 → 25/36 | 3/40 → 3/40 |
| v5 | 31/40 → 28/40 | 6/10 → 5/11 | 5/30 → 6/29 | 25/40 → 22/36 | 6/40 → 6/40 |
| Base + evidence prompt (Issue 1) | 24/40 → 13/40 | 2/10 → 2/11 | 28/30 → 26/29 | 18/40 → 16/36 | 29/40 → 29/40 |
| NLI gate (Issue 1) | 32/40 → 32/40 | 3/10 → 4/11 | 1/30 → 0/29 | 24/40 → 24/36 | 22/40 → 22/40 |

### Main sensitivity finding: NLI's relative standing improves

Under proxy `action_ok`, NLI trails v6 seed 0 by 3 rows (32 versus 35) and v6 seed 1 by 2 rows (32 versus 34). Under AI-adjudicated labels, NLI remains 32/40, ties v6 seed 0, and trails v6 seed 1 by only 1 row (32 versus 33). Thus the trained-v6-versus-NLI `action_ok` gap narrows from **3 → 0 rows for seed 0** and **2 → 1 row for seed 1**. NLI also remains above v5 (32 versus 28), improves valid uptake from 3/10 to 4/11, records zero unwarranted updates (0/29), and ties v6 seed 0 on post-feedback accuracy (24/36).

This does **not** make NLI uniformly best or erase the trained models' advantages: v6 seed 1 retains the highest `action_ok` (33/40) and post-feedback count (25/36), and both v6 seeds have higher valid uptake than NLI. The prompted base drops sharply on `action_ok` (24/40 → 13/40), so the trained-versus-prompted-base separation remains large. These are descriptive changes on 40 AI-reviewed rows, not significance tests or fresh validation.

## Recompute and verification

From `release_staging/`:

```bash
python3 -I -B code/annotation/ai_reference/recompute.py --root dataset/reproduction --check
```

The staged recompute reads the sanitized merged annotations and stored predictions, checks the AI-only provenance fields, and must reproduce `recompute.json` exactly. The full `release_staging/verify_staging.py` gate includes this check.

## Limitations

- **AI-only labels:** both annotators and the adjudicator were models. Human A/B annotation, human agreement, human adjudication, and merged human labels remain pending; Issue #3 is not complete.
- **Small, non-fresh scope:** 40 non-fresh rows only. This is a sensitivity analysis of stored outputs, not human gold or independent validation, and it says nothing direct about fresh-set performance.
- **Shared semantic judgment:** all seven adjudications adopt one model's interpretation of consent-only prohibitions. Model agreement may share correlated errors and is not a substitute for legal or human review.
- **Proxy and protocol differences:** some changes reflect v1 proxy versus v2 action semantics, not disagreement about the underlying text.
- **Arm coverage:** the base arm is the Issue 1 evidence-prompted base, not a new raw base-Aya run. No new inference or fresh labelling was performed.
