# EvidenceTune — written execution plan

## Objective

Deliver an official Track 2a #2 labelled safety benchmark and report, then test whether a SafeTune-hardened Aya adapter can outperform base Aya, ordinary SFT, and inference-only harnesses without sacrificing task utility (secondary Track 2b #5).

## Ownership

| Category | Owner scope | Primary deliverables |
|---|---|---|
| **Data & Annotation** | Sources, counterfactuals, labels, Arabic quality, CuratorKIT | Versioned train/dev/test datasets, annotation guide, adjudicated labels, manifests |
| **ML & Evaluation** | Aya runners, SafeTune, baselines, AuditKIT, analysis | Adapters, raw outputs, comparison runs, operating curves, technical report |
| **Frontend & Design** | Demo experience, visual communication, public presentation | Browser demo, matched-pair story, scoreboard, demo-day flow |

## Milestones

### M1 — End-to-end smoke test

Build 12 development cases covering valid low-overlap corrections, unsupported high-overlap corrections, and bare pressure. Define the data/schema contract, run a tiny SafeTune job, load the resulting CuratorKIT export in AuditKIT, and save a static matched-pair demo.

**Exit criteria:** all three repository handoffs work; labels and predictions survive intact; standalone and AuditKIT metrics match; no final-test cases are used.

### M2 — Dataset and independent answer key

Select sources and create counterfactual conversations across document reasoning, multi-hop/table/arithmetic, and native-Arabic comprehension. Write the annotation guide and label truth, evidence sufficiency, answerability, and acceptable action sets separately. Double-label blind to model outputs, adjudicate disagreements, and publish agreement/exclusions.

Split train/dev/test by source document and hypothesis template. Add the frozen held-out-domain and Arabic-register transfer suite.

**Exit criteria:** lexical controls pass manual review; split leakage checks pass; labels are reproducible; CuratorKIT manifests and checksums verify.

### M3 — Training and baseline tournament

Run base Aya, always/never update, lexical/embedding/entailment methods, evidence-aware prompting, generic Aya review, and the verify/update/clarify harness. Train ordinary SFT and SafeTune adapters using identical data partitions. Preserve configurations, seeds, decoding settings, and raw generations.

**Exit criteria:** every comparator runs on identical development cases; utility-retention data remains effective; the strongest harness and its coverage/latency operating point are identified.

### M4 — Frozen final evaluation

Freeze cases, prompts, thresholds, analysis code, seeds, decoding, exclusion rules, and primary comparisons before final outputs. Run the untouched test and transfer suites once per preregistered configuration. Compute valid uptake, UUR, post-interaction accuracy, solo coverage, clarification outcomes, cost, and paired case-clustered intervals.

**Exit criteria:** AuditKIT reproduces the standalone scorecard; no post-final threshold selection is presented as confirmatory; negative and null results remain visible.

### M5 — Demo, report, and submission

Build the three-panel matched-pair demo: base failure, differentiated response, final task outcome. Add the comparator scoreboard and link each displayed result to AuditKIT/CuratorKIT artifacts. Write the HF Article with rationale, metrics, limitations, and honest claims. Package the dataset, adapter if successful, logs, code, and report for release.

**Exit criteria:** the demo works from saved artifacts; claims match frozen results; feature freeze targets 12 Nov and submission targets 13 Nov, ahead of the official 14 Nov deadline.

## Shared contracts

- **Case schema:** stable case ID, source/provenance, original answer, truth target, evidence, feedback condition, split, and annotation fields.
- **Action schema:** update, retain, or clarify; optional citation/evidence request; final resolution and utility fields.
- **Run schema:** model/adapter, policy, prompt, seed, decoding, threshold, timestamp, raw output, parsed action, latency, and errors.
- **Artifact contract:** CuratorKIT exports are the only evaluation input; AuditKIT reads those exports directly; the demo reads saved AuditKIT results rather than recomputing headline metrics.

## Decision rules

1. If annotators cannot produce reliable labels after one guide revision, stop and redesign the construct.
2. If lexical similarity solves the counterfactuals, rebuild the data rather than tune on final outputs.
3. If SafeTune only trades utility for lower UUR, report the trade-off and do not claim a superior policy.
4. If the strongest cheap harness wins at matched coverage/latency, submit the benchmark/harness result without a trained-model-superiority claim.
5. If repository artifacts cannot reproduce standalone results, block release claims until fixed.

## Scope cuts

- **50% scope:** two domains, one Aya model/seed, no optional clarification turn. Retain lexical controls, independent labels, ordinary-SFT comparison, utility metrics, and all three repositories.
- **25% scope:** benchmark/report plus inference harness, one Aya model/seed, static saved-output demo. Make no trained-model claim without adapter results.
- **Never cut:** independent answer key, untouched final evaluation, raw artifacts, final-task/solo utility, strongest cheap baseline, or honest limitations.

See [BACKLOG.md](BACKLOG.md) for actionable tasks and [SPEC.md](SPEC.md) for the research specification.
