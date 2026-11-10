# Contradiction interpolation spike — 10 Nov 2026

**Decision: KILL for both candidates. Retain merged alpha=0.75.** Uniform interpolation did not combine static Contradiction gains with acceptable dialogue behavior. No training, frozen evaluation, or public model replacement occurred.

## Fixed recipes

For candidate weight `w`, each tensor is `(1-w) * merged_alpha_0.75 + w * contradiction_sft`, using float64 arithmetic and one cast back to source dtype.

- Merged adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.
- Contradiction candidate SHA-256: `4ba9fce20fb0d4f81c0a4023096a3cf11bdd7c75e7d6335661bc825f29699ce1`.
- Exactly two candidates: `w=0.25` and `w=0.50`; no additional alpha search.
- Dev-only Apple MPS bf16 evaluation, with the original Contradiction retention/resolution gates.

## Results

| Candidate | Semantic task success | Targeted task success | Resolution overall | Decision |
|---|---:|---:|---:|---|
| Merged baseline | 96.25% | 90.00% | 79.41% | Retain |
| 25% Contradiction candidate | 96.67% | 90.00% | 75.00% | FAIL |
| 50% Contradiction candidate | **98.75%** | **91.67%** | **71.21%** | FAIL |

### 25% candidate

- Contradiction task-success gain: +1.429pp, below the required +3pp.
- Contradiction all-five gain: +9.524pp.
- Resolution delta: −4.412pp.
- Final-dialogue delta: −2.344pp.
- Violations: insufficient Contradiction gain, resolution decline, and final-dialogue decline beyond 2pp.

### 50% candidate

- Contradiction task-success gain: +4.762pp; all-five gain: +16.667pp.
- Contradiction pair gain: +7.143pp; action gain: +4.762pp.
- Pooled Entailment delta: −0.476pp, but targeted Entailment delta: −2.222pp.
- Resolution delta: **−8.200pp**; final-dialogue delta: **−4.688pp**.
- Violations: resolution decline, final-dialogue decline beyond 2pp, and targeted-Entailment regression.

The observed direction is monotonic: increasing candidate weight improves static scores while worsening resolution. Interpolation does not correct the over-clarification tradeoff.

## Evidence

- Selection: `.combine_spike/local_results/evaluation/selection.json`.
- Summary: `.combine_spike/local_results/evaluation/summary.json`.
- Run plan SHA-256: `ab570326bfdd707951924f5618784666002ff652baa6033f9a2303af3076f6a2`.
- Selection records `selected_model=merge_alpha_0.75` and `new_frozen_generation_started=false`.
- Raw dev predictions, summaries, and generation logs are preserved under `.combine_spike/local_results/`.
- Candidate tensor files are regenerable from the two retained source adapters and the fixed recipes above.

## Recommendation

Stop. Neither candidate earns independent confirmation. Do not replace the public adapter or reinterpret static gains as a full-policy improvement.
