# Natural-domain near-miss data — 9 Nov 2026

**Verdict: do not train or score against this pack.** Four generations were built and independently reviewed. The final generation has 113 cases / 565 rows (65 train, 20 dev, 28 frozen), but full independent review of all 113 cases and 226 near-misses still finds fundamental scope and label ambiguity.

## What happened

- Initial pack: 199 cases / 995 rows.
- Independent reviews rejected cases for actor/identifier mismatches, unsupported aliases, missing domain restrictions, composite outcomes, population and modality overgeneralization, and causal/association confusion.
- Generation 4 removed all flagged cases and performed exhaustive visible-text review of every remaining case and both near-misses.
- Structural, provenance, freshness, deterministic and contract checks pass. Semantic truth/sufficiency does not pass.

## Independent conclusion

The surviving claims still require inconsistent judgments about cohort/country/population scope, association versus causation, composite mechanisms, model/subtype restrictions, aliases and malformed upstream claims. This is not a bounded remediation problem.

**Do not create generation 5.** Valid alternatives are:
1. independent expert reannotation with explicit scope rules and an uncertainty class; or
2. relabel the artifact strictly as **SciFact source-label/proxy consistency**, not strict truth evaluation.

The merged α=0.75 adapter remains the selected model. DPO also failed to improve it. No training or publication occurred.

Artifacts: `natural_data/`, `natural_data_review/REVIEW-V4.md`, `natural_data_review/findings_v4.json`.
