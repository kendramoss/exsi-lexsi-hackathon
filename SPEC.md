# EvidenceTune — project specification

**One-line pitch:** A lexical-controlled counterfactual benchmark and SafeTune-trained Aya adapter that learns when to accept evidence, resist unsupported correction, and ask for clarification—without sacrificing task utility.

**Official fit:** primary Track 2a **#2** (labelled/scored benchmark, dataset + report); secondary **#5** (hardened versus ordinary fine-tuning). Deliverables: dataset/report, adapter, evaluation logs, and demo. **CuratorKIT → SafeTune → AuditKIT** are all load-bearing.

## Research question

Can Aya learn **evidence-sensitive correction** rather than indiscriminate capitulation or blanket stubbornness, and can that improvement survive lexical shortcuts and cheap inference-only alternatives while preserving final task utility?

A correct-direction answer flip alone does not show that feedback warranted the update. EvidenceTune evaluates the complete interaction: whether the model updates, retains, or asks for evidence appropriately, and whether the conversation ultimately resolves the task.

## Motivation

Tiny Aya pilots accepted valid, fabricated, and bare-pressure corrections indiscriminately. A TF-IDF gate improved selectivity but sacrificed valid uptake and post-feedback accuracy:

| Frozen-final proxy metric | Base Aya | TF-IDF-gated |
|---|---:|---:|
| Unwarranted-update rate ↓ | 100% | 7.14% |
| Evidence-selective accuracy ↑ | 20% | 87.14% |
| Valid uptake ↑ | 100% | 64.29% |
| Post-feedback accuracy ↑ | 60% | 52.86% |

EvidenceTune therefore changes the construct and mechanism rather than presenting that gate as the solution. Existing pilots are **motivation only**, not confirmatory evidence for the new concept.

## Design

### 1. Defeat lexical shortcuts by construction

Every evaluation family includes matched counterfactuals:

- low-overlap valid paraphrases;
- high-overlap unsupported corrections;
- multi-hop evidence;
- executable numeric/table corrections;
- bare-pressure and pressure-away-from-truth controls.

Surface similarity cannot determine warrant. Non-gold citations never automatically count as non-warrants.

### 2. Separate evidence from acceptable behaviour

Annotators label three things independently:

1. **Truth/correction target:** what answer the evidence supports.
2. **Evidence sufficiency and answerability:** supported, contradicted, insufficient/partial, or absent; whether the available context can settle it.
3. **Acceptable action set:** update with citation, retain with explanation, and/or ask one targeted evidence question.

Partial evidence can permit several reasonable actions; it must not be forced into an unstable single dialogue-level label. Two annotators work blind to model outputs, with adjudication, agreement, and exclusions published. Native-Arabic cases are independently authored and labelled, not merely translated.

### 3. Optimise resolution, not rejection

The policy can update, retain, or clarify. Clarification is not inherently good: it earns credit only when targeted and when the complete interaction resolves successfully under explicit call, clarification, latency, and user-effort budgets. Unnecessary clarification and selective deferral remain visible failures.

### 4. Make training load-bearing

- **CuratorKIT:** validates source cases and schema, preserves independent labels/provenance, exports counterfactual SFT conversations, utility-retention examples, and the untouched evaluation pack with manifests/checksums.
- **SafeTune:** after a custom-schema smoke test, preprocess into documented task/safety datasets and train a small LoRA hardening adapter. SafeTune is a method library, not a native warrant pipeline; the thin schema adapter is project code.
- **AuditKIT:** loads CuratorKIT's actual held-out export and compares base Aya, ordinary SFT, SafeTune, and inference-only policies on identical cases; saves raw predictions, metrics, configurations, fingerprints, and paired comparisons.

No CircuitKIT or mechanistic claim. No claim that SafeTune natively understands warrant labels.

## Frozen evaluation protocol

The final test targets **120 fresh base cases** across document reasoning, multi-hop/table/arithmetic, and native-Arabic comprehension, each with matched interventions. Train/dev/test are disjoint by source document and hypothesis template; recurring templates cannot leak across partitions.

Add a separately frozen **transfer suite** of independently labelled corrections in held-out domains and Arabic registers. Retain identical warrant definitions, lexical controls, utility endpoints, and harness comparisons. This tests whether the model learned correction behaviour rather than dataset-specific evidence rituals.

Freeze before seeing final outputs: sources, cases, annotation guide, prompts, seeds, decoding, thresholds, analysis code, operating points, exclusion rules, and primary comparisons. Preserve raw generations and labels.

## Strongest cheap baselines

- always-update and never-update;
- TF-IDF/lexical overlap and embedding similarity;
- off-the-shelf entailment;
- generic Aya reviewer and evidence-aware prompting;
- ordinary SFT;
- full verify/update/clarify inference harness.

The trained adapter must beat the **strongest evidence-aware harness at matched coverage and latency**, not merely base Aya. If the harness wins, the benchmark/report remains a valid #2 contribution, but no trained-model-superiority claim survives.

## Metrics and success criterion

**Primary:** valid uptake, unwarranted-update rate (UUR), and post-interaction task accuracy including clarification answers.

**Secondary:** solo accuracy/coverage, evidence-selective accuracy, clarification rate, unnecessary-clarification rate, successful subsequent resolution, user effort, inference calls/latency, and per-language/domain/transfer results.

Report paired case-clustered intervals and full operating curves. Compare at matched uptake/coverage where possible; otherwise show nearest operating points and the complete curve.

**Practical target:** Pareto improvement over base and never-update—lower UUR **without reducing valid uptake, final task accuracy, or solo coverage**—and dominance over the strongest evidence-aware harness at matched coverage/latency before claiming a superior trained policy.

## 60-second demo

Use one three-panel matched pair with identical correction targets:

1. **Base failure:** Aya accepts both a low-overlap valid paraphrase and a high-overlap unsupported correction.
2. **Differentiated response:** EvidenceTune accepts and cites the valid correction, then asks targeted evidence for the unsupported one. Resolve the clarification from saved outputs; show unnecessary clarification beside UUR.
3. **Final outcome and audit:** reveal completed task accuracy, valid uptake, UUR, solo coverage, and cost for base, ordinary SFT, SafeTune, and the strongest harness; open the CuratorKIT manifest and AuditKIT comparison for those exact records.

The resolved conversation is the headline; the scoreboard is subordinate. Static/recorded execution is acceptable.

## Three-person implementation plan

1. **Data/annotation owner:** source selection, counterfactual generation, annotation guide, blind double-labelling, adjudication, transfer suite, Arabic quality, CuratorKIT manifests.
2. **Training/baselines owner:** SafeTune schema adapter and smoke test, LoRA/ordinary-SFT runs, Aya runners, prompting/entailment/harness baselines, seeds/decoding/raw-output logs.
3. **Audit/demo owner:** AuditKIT metrics and paired comparisons, operating curves/CIs, reproduction checks, browser demo, HF Article/report assembly.

Shared first milestone: a 12-case end-to-end smoke test proving the CuratorKIT→SafeTune→AuditKIT handoffs before full annotation/training. Shared final milestone: one untouched final run, hash verification, and independent reproduction from the exported artifacts.

## Scope-cut ladder

- **50%:** two domains, one Aya model/seed, optional clarification turn dropped. Retain lexical controls, independent labels, ordinary-SFT comparison, utility endpoints, strongest remaining baselines, and all three repositories.
- **25%:** official #2 benchmark/report plus inference harness, one Aya model/seed, static demo over saved outputs. Do not claim trained-model improvement without adapter results.
- **Never cut:** independent answer key, lexical controls, untouched final evaluation, raw artifacts, solo/final-task utility, strongest cheap comparison, honest limitations, and genuine repository handoffs.

## Stop conditions

1. Annotators cannot separate truth, evidence sufficiency, answerability, and acceptable actions reliably after one guideline revision.
2. Counterfactuals remain solvable by surface similarity; rebuild the construct rather than tune on final outputs.
3. SafeTune's custom-schema smoke test cannot preserve labels and utility-retention examples through training.
4. The adapter only trades valid uptake/final-task accuracy for lower UUR, or loses to the strongest harness at matched coverage/latency; publish the benchmark/harness result, not a model-superiority claim.
5. CuratorKIT/AuditKIT artifacts cannot reproduce the standalone scorecard exactly; block submission claims until fixed.

## Deliberately excluded

- No semantic claim from non-gold citation IDs alone.
- No claim that clarification is beneficial without subsequent resolution and cost accounting.
- No credit for SafeTune merely being invoked; ordinary SFT and cheap harnesses are required comparators.
- No broad multilingual/generalisation claim without the frozen transfer results.
