# EvidenceTune abstract

EvidenceTune addresses sycophantic correction: an assistant changes its answer when a user applies pressure, regardless of whether the supplied evidence justifies the change. The project combines a matched five-condition benchmark with a Tiny Aya Global LoRA adapter trained to `UPDATE` on sufficient evidence, `CLARIFY` or `RETAIN` on insufficient citations, and `RETAIN` under bare pressure. CuratorKIT supplies validated exports and provenance, SafeTune trains the source adapters, and AuditKIT supplies source-model evaluations.

The current candidate, `merge_alpha_0.75`, interpolates 75% v7 semantic-contrast weights and 25% v8 targeted/two-turn weights. Dev-only selection chose it after preregistered retention and resolution gates. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.**

On Apple MPS bf16 frozen confirmation, merged versus v7 semantic task success is **92.50% versus 88.75%**, targeted task success **93.70% versus 91.48%**, semantic all-five case success **72.92% versus 60.42%**, and targeted all-five case success **79.63% versus 74.07%**. Dev resolution is **27/34 (79.41%)** for merged and **38/50 (76.00%)** for v7. Resolution is conditional on CLARIFY episodes, so these denominators differ and are not paired outcomes. Raw base Tiny Aya was not evaluated on current contract-v2 suites; base→merged correction improvement is therefore unmeasured.

Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers, not AuditKIT. A stdlib raw-record validator replays selection and frozen metrics from 3,120 single-turn records plus five resolution arms. The original selection-code bytes cannot be recovered; later frozen-support/cache-fixed code is not represented as that original code.

All 1,020 frozen records were checked, and the adapter and evaluation artifacts retain hashes, provenance, same-run baselines, and a recorded-only demo for inspection.

DPO and natural SciFact training were rejected. Contradiction and Arabic weaknesses remain. All current labels are synthetic/proxy or AI-reviewed, not human-validated or broad natural-domain evidence. The adapter is CC BY-NC 4.0; original project code is MIT licensed, with dataset and Lexsi terms preserved separately.

**Public artifacts:** [model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75), [dataset/evidence](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75), [collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08), and [recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html). Team submission source: [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon).
