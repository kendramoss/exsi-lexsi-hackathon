---
pretty_name: "EvidenceTune merged alpha=0.75 evidence and training data"
license: other
viewer: false
---

# EvidenceTune merged-model dataset collection

## Contents

This public dataset/evidence bundle contains contract-v2 semantic and targeted source/label packs, native-resolution packs, the authored Issue10 synthetic pack, the small Arabic proxy pack and review, historical v6 data, and exact curated v7/v8 SafeTune training inputs. Manifests, hashes, freeze records, freshness evidence, and CuratorKIT provenance are retained where available.

## Dataset viewer

The Hub viewer is intentionally disabled with `viewer: false` because this is a heterogeneous evidence bundle, not a single tabular dataset with compatible schemas and configs. Interactive previews are therefore unavailable; all source files remain downloadable, with collection-relative `manifest.json` and `SHA256SUMS` inventories for integrity verification.

## Label and use boundaries

Labels are dataset or synthetic construction proxies and independent AI review, not independent human ground truth. Issue #12 labels remain `independent_ai_review` until humans approve them. Five matched rows per case are correlated. The packs support narrow correction-contract research, not broad natural-domain or human-validated performance claims. Frozen cases are evaluation-only: never train, tune, prompt-select, or reselect on them.

DPO and natural SciFact training were rejected; rejected natural-data packs are not included. Contradiction and Arabic weaknesses remain. Arabic review is provisional and not native-speaker adjudication.

AuditKIT produced source-model evaluations. Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers, not AuditKIT. CircuitKIT is historical original-v6 smoke only.

## Licensing and attribution

- ContractNLI: CC BY 4.0, https://github.com/stanfordnlp/contract-nli
- VitaminC: CC BY-SA 3.0, https://github.com/TalSchuster/VitaminC
- AraStance: CC BY 4.0, https://github.com/Arabic-NLP/AraStance
- Original English XSTest: CC BY 4.0, Röttger et al., https://github.com/paul-rottger/xstest
- XSTest-IT: CC BY 4.0 according to dataset-card metadata, https://huggingface.co/datasets/saiteki-kai/XSTest-IT

Korean XSTest_ko had no declared license. Korean raw rows are excluded. The `overrefusal/prompts.en_it.jsonl` file is a derived copy retaining original English/Italian JSONL row bytes; its derivation JSON identifies the unchanged source, counts, and hashes.

Original EvidenceTune code is MIT licensed, and the adapter is separately CC BY-NC 4.0. Dataset material is not relicensed under either; the mixed upstream terms are why this card declares `license: other`. See [NOTICE.md](NOTICE.md), [LICENSE-DECISION.md](LICENSE-DECISION.md), and applicable upstream terms. Team source repository: [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon).
