# CircuitKIT compatibility smoke — 7 Nov 2026

**Result: PASS.** Tiny Aya Global + the v6 LoRA loaded into CircuitKIT's `HookedTransformer` (Cohere2ForCausalLM, 36 layers, bf16). Four non-fresh matched cases / 8 rows were evaluated; hidden states were captured at layers 0, 17 and 35 (12 comparisons). No training and no fresh cases.

The one bounded activation patch completed at `blocks.35.hook_resid_post`, recipient prompt position 617:

- Valid-case mean-logprob metric: **2.431584**
- Unsupported-case metric: **−5.726725**
- Patched unsupported metric: **2.431569**
- Normalized recovery: **0.999998** on this single example

The metric is `mean_logprob(UPDATE) − mean_logprob(CLARIFY)` using teacher-forced continuation scoring. Boundary-robust tokenization used `ACTION:` plus space-prefixed actions, with exact token IDs/common-prefix lengths recorded.

**Interpretation:** this confirms API compatibility and that a single residual patch can change the measured action preference in one example. It is not a circuit/mechanistic finding and does not justify a broad causal claim. A larger activation-patching analysis is optional and should use multiple held-out cases before any such claim.

Raw artifact: `circuit_smoke/output_final/smoke_result.json`. CircuitKIT commit `e71d5e17fe6e2abfde47ec9a7fbaf31649601b78`.
