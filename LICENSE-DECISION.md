# License decision

> **Chronology:** this decision was recorded before initial publication. The merged model, dataset/evidence bundle, collection, and demo were subsequently published on 10 Nov 2026; `PUBLICATION-RESULTS.json` records their verified URLs and revisions. This document remains the license decision record, not a claim that the artifacts are still unpublished.

## Original project code: MIT selected

The user explicitly selected the **MIT License** for EvidenceTune's original project code on 10 Nov 2026. `LICENSE` contains the MIT terms with copyright `2026 EvidenceTune contributors`.

MIT applies only to original EvidenceTune code and documentation for which the contributors hold the relevant rights. It does **not** relicense third-party code, Lexsi toolkits or modifications derived from them, model weights, datasets, prompts, or third-party raw outputs.

## Merged adapter: CC BY-NC 4.0

The merged alpha=0.75 adapter is marked **`license: cc-by-nc-4.0`** in the real model card installed at the packaged adapter root. Tiny Aya Global is attributed to **Cohere Labs** / `CohereLabs/tiny-aya-global`. Adapter licensing remains separate from the MIT code license. See `LICENSE-MODEL` and `NOTICE.md`.

## Datasets and prompts

Upstream terms travel with their corresponding collections and notices:

- ContractNLI: CC BY 4.0.
- VitaminC: CC BY-SA 3.0.
- AraStance: CC BY 4.0.
- Original English XSTest: CC BY 4.0.
- XSTest-IT: CC BY 4.0 according to its dataset-card metadata.
- Korean XSTest_ko: no declared license was found. **All Korean raw prompts, responses, source rows, and review rows are excluded from publishable staging unless the license is resolved.** Aggregate historical statistics may be reported with that limitation; no Korean raw rows are staged.

Natural SciFact training was rejected and its pack is not included in the model-training or public dataset staging. AI/synthetic labels remain proxies, and Issue #12 labels remain `independent_ai_review` until human approval.

## Lexsi and other third-party code

CuratorKIT, SafeTune, and AuditKIT remain under their applicable Lexsi Labs Source Available Licenses (LSAL), not MIT. Local bug fixes, wrappers, and modifications must retain the applicable LSAL notices and modification markings when those third-party works are redistributed. No Lexsi toolkit source tree is vendored into the raw-free adapter release. `NOTICE.md` records the versions and the public staging includes the applicable license texts for reference.

CircuitKIT evidence is historical original-v6 compatibility smoke only; no CircuitKIT source is added to this package.

## Publication gate

Before public release, a human must verify the license files, dataset-card attributions, source/label provenance, exclusion of Korean raw rows, and the separation among MIT code, CC BY-NC adapter weights, dataset terms, and Lexsi LSAL code. This local decision record is not legal advice and does not authorize publication by itself.
