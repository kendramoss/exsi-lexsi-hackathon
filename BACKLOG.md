# EvidenceTune — task backlog

**Priority:** P0 = end-to-end smoke test; P1 = required for the full submission; P2 = polish after the core works.

## Data & Annotation

- [ ] **DA-01 — Define case, action, and annotation schemas** · P0  
  Specify stable IDs, provenance, truth target, evidence sufficiency, answerability, acceptable action set, feedback condition, and split. **Done when:** example records validate and all owners approve the contract.

- [ ] **DA-02 — Author 12 development smoke cases** · P0 · Depends on DA-01  
  Include low-overlap valid corrections, high-overlap non-warrants, and bare pressure. **Done when:** all conditions have independent answer keys and no final-test source is used.

- [ ] **DA-03 — Build the licensed source pool** · P1 · Depends on DA-01  
  Collect document, multi-hop/table/arithmetic, and native-Arabic source material with provenance. **Done when:** every source permits the intended use and has a stable identifier.

- [ ] **DA-04 — Generate matched counterfactual families** · P1 · Depends on DA-03  
  Hold each target fixed while varying feedback across all preregistered conditions. **Done when:** lexical review confirms that overlap alone cannot determine the label.

- [ ] **DA-05 — Write and pilot the annotation guide** · P0 · Depends on DA-01  
  Define supported, contradicted, insufficient/partial, absent, answerability, and acceptable actions with edge examples. **Done when:** two annotators can label the smoke cases without seeing model outputs.

- [ ] **DA-06 — Run blind double-labelling and adjudication** · P1 · Depends on DA-04, DA-05  
  Preserve raw labels, disagreements, adjudication, agreement, and exclusions. **Done when:** the release label set is independently reproducible.

- [ ] **DA-07 — Create leakage-safe splits and transfer suites** · P1 · Depends on DA-04  
  Split by source and hypothesis template; freeze held-out-domain and Arabic-register transfer cases. **Done when:** automated and manual checks find no source/template leakage.

- [ ] **DA-08 — Implement the CuratorKIT export** · P0 · Depends on DA-02  
  Validate records, preserve labels/provenance, and emit manifests/checksums. **Done when:** the 12-case export round-trips without field loss and rejected rows are explained.

- [ ] **DA-09 — Freeze and export final dataset packs** · P1 · Depends on DA-06, DA-07, DA-08  
  Produce train/dev/test/transfer packs with immutable hashes. **Done when:** final hashes are recorded before model outputs are inspected.

## ML & Evaluation

- [ ] **ML-01 — Establish reproducible repository environments** · P0  
  Pin CuratorKIT, SafeTune, AuditKIT, model, and dependency versions. **Done when:** a clean setup command runs the smoke workflow and records versions.

- [ ] **ML-02 — Build the permitted Aya runner** · P0 · Depends on DA-02  
  Save prompts, seeds, decoding, raw generations, parsed actions, latency, and errors. **Done when:** repeated smoke runs are traceable to exact configurations.

- [ ] **ML-03 — Implement the reference metric suite** · P0 · Depends on DA-01  
  Compute valid uptake, UUR, evidence-selective accuracy, post-interaction accuracy, solo coverage, clarification outcomes, and cost. **Done when:** hand-scored smoke cases match exactly.

- [ ] **ML-04 — Adapt the schema and smoke-test SafeTune** · P0 · Depends on DA-08, ML-02  
  Preprocess counterfactual and utility-retention examples into documented SafeTune task/safety datasets and run a tiny LoRA job. **Done when:** the adapter loads and training preserves the intended labels/actions.

- [ ] **ML-05 — Connect CuratorKIT exports to AuditKIT** · P0 · Depends on DA-08, ML-03  
  Evaluate identical exported records and save predictions, metrics, fingerprints, and comparisons. **Done when:** AuditKIT reproduces every reference smoke metric with correct optimization directions.

- [ ] **ML-06 — Implement cheap and inference-only baselines** · P1 · Depends on ML-02, ML-03  
  Add always/never, TF-IDF, embeddings, entailment, evidence-aware prompting, generic Aya review, and verify/update/clarify. **Done when:** every baseline reports safety, utility, coverage, and latency.

- [ ] **ML-07 — Train the ordinary-SFT comparator** · P1 · Depends on DA-09  
  Use the same training partition and comparable optimization budget as the hardened run. **Done when:** the adapter and complete configuration are reproducible.

- [ ] **ML-08 — Train SafeTune candidates on development data** · P1 · Depends on ML-04, DA-09  
  Preserve utility-retention data and record all candidate configurations without touching final outputs. **Done when:** the preregistered candidate is selected using development criteria only.

- [ ] **ML-09 — Run the development baseline tournament** · P1 · Depends on ML-06, ML-07, ML-08  
  Compare base, ordinary SFT, SafeTune, and inference-only policies across operating points. **Done when:** the strongest harness and matched coverage/latency comparisons are identified.

- [ ] **ML-10 — Freeze and execute final evaluation** · P1 · Depends on DA-09, ML-09  
  Freeze prompts, thresholds, seeds, analysis, exclusions, and comparisons before one untouched test/transfer run. **Done when:** raw outputs and run manifests are immutable and no post-final selection is mislabeled confirmatory.

- [ ] **ML-11 — Produce final analysis and claim table** · P1 · Depends on ML-10  
  Compute paired case-clustered intervals, operating curves, per-domain/language/transfer results, and negative findings. **Done when:** every report/demo claim links to an AuditKIT result.

- [ ] **ML-12 — Independently reproduce the exported results** · P1 · Depends on ML-11  
  Rebuild the scorecard from CuratorKIT/AuditKIT artifacts in a clean environment. **Done when:** hashes, predictions, metrics, and headline tables match exactly.

## Frontend & Design

- [ ] **FD-01 — Wireframe the three-panel demo story** · P0  
  Design base failure → differentiated response → final task outcome, with the scoreboard subordinate to the conversation. **Done when:** all owners approve the 60-second flow and claim labels.

- [ ] **FD-02 — Build the static smoke demo** · P0 · Depends on FD-01, ML-05  
  Render one matched pair from saved smoke artifacts. **Done when:** valid and unsupported corrections are visibly distinguished without live model calls.

- [ ] **FD-03 — Build the case and provenance browser** · P1 · Depends on FD-02  
  Browse condition, label, model action, citation/clarification, source, and artifact hash without exposing hidden test answers during runs. **Done when:** every displayed case resolves to its exported record.

- [ ] **FD-04 — Implement the resolved-conversation panel** · P1 · Depends on ML-09  
  Show update/retain/clarify, the evidence answer, subsequent resolution, and unnecessary-clarification outcomes. **Done when:** clarification is never presented as successful without final resolution.

- [ ] **FD-05 — Implement the comparator scoreboard** · P1 · Depends on ML-11  
  Display valid uptake, UUR, final accuracy, solo coverage, latency, and operating points for all required comparators. **Done when:** trade-offs and intervals are visible and no single score hides utility loss.

- [ ] **FD-06 — Create report and demo-day visual assets** · P1 · Depends on FD-05  
  Produce the matched-pair graphic, pipeline diagram, concise limitations panel, and 60-second script. **Done when:** the recorded fallback and live presentation tell the same story.

- [ ] **FD-07 — Polish accessibility and responsive behaviour** · P2 · Depends on FD-03, FD-05  
  Check keyboard navigation, contrast, mobile layout, reduced motion, and readable tables. **Done when:** the core demo works without animation or hover-only interactions.

## Cross-category completion gate

The submission is ready only when DA-09, ML-12, and FD-06 are complete, all P0/P1 stop conditions have been checked, and every public claim matches the frozen artifacts.
