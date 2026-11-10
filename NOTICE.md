# EvidenceTune attribution and third-party notices

## Code and model

- Original EvidenceTune project code: Copyright (c) 2026 EvidenceTune contributors; MIT License in `LICENSE`. This does not cover third-party code or data.
- EvidenceTune merged alpha=0.75 adapter: CC BY-NC 4.0; see `LICENSE-MODEL`.
- Tiny Aya Global is developed by **Cohere Labs**. Base model: https://huggingface.co/CohereLabs/tiny-aya-global. The merged adapter is a modification/interpolation of LoRA adapters derived from Tiny Aya Global and is not endorsed by Cohere Labs.

## Datasets and prompts

- **ContractNLI**, CC BY 4.0: https://github.com/stanfordnlp/contract-nli. Used for historical contract cases and derived synthetic correction tasks. Gold spans/labels are proxies, not independent human validation of EvidenceTune outputs.
- **VitaminC**, CC BY-SA 3.0: https://github.com/TalSchuster/VitaminC. Used for topic-diverse historical contrastive data. Share-alike obligations apply to applicable derived dataset material.
- **AraStance**, CC BY 4.0: https://github.com/Arabic-NLP/AraStance. Used by the small provisional Arabic proxy pack. Source overlap and possible translation caveats remain; native-speaker adjudication is absent.
- **XSTest**, Röttger et al., CC BY 4.0: https://github.com/paul-rottger/xstest. Original safe English prompts used in the over-refusal proxy.
- **XSTest-IT**, CC BY 4.0 according to its dataset-card metadata: https://huggingface.co/datasets/saiteki-kai/XSTest-IT. Third-party Italian translation; full translation equivalence was not audited.
- **XSTest_ko**: no declared license was found. Korean raw prompts, responses, source rows, and review rows are excluded from publishable staging. Do not add them until permission/license is resolved.
- Natural SciFact data generation was rejected and is not staged as a training pack. Do not treat rejected natural-data artifacts as validated evaluation data.

## Lexsi toolkit code and modifications

The Lexsi works are owned by **Lithasa Technologies Pvt. Ltd.** and are **not** MIT licensed:

- **CuratorKIT** © 2026 Lithasa Technologies Pvt. Ltd.; Lexsi Labs Source Available License (LSAL) v1.1.
- **SafeTune** © 2026 Lithasa Technologies Pvt. Ltd.; LSAL v1.2.
- **AuditKIT** © 2026 Lithasa Technologies Pvt. Ltd.; LSAL v1.2.

EvidenceTune used CuratorKIT for validated exports/provenance, SafeTune for source-adapter training, and AuditKIT for source-model evaluations. Local modifications include the SafeGrad masked per-token KL fix and AuditKIT model-identity cache workaround. Any redistribution of Lexsi code or derivative modifications must retain the applicable LSAL text and mark the modification. Organization acknowledgement/permission and commercial restrictions are specified by those licenses; this package does not grant additional rights.

AuditKIT did **not** produce the current merged-model scores. Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used EvidenceTune's custom contract-v2/native scorers. CircuitKIT results are historical original-v6 compatibility smoke only.

## Public staging exclusion and privacy

Public staging is generated locally with an allowlist. Credential files, environment files, caches, vendor dependencies, Korean raw rows, rejected natural SciFact packs, and unresolved/private material are excluded. Historical artifacts may contain original absolute experiment paths for audit; the staging manifest itself uses portable relative paths and hashes.
