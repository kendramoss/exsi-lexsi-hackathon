# EvidenceTune publication checklist — local preparation only

No item below authorizes a push, upload, collection, public-link update, or external contact. Complete and review locally first.

## Verified publication status — 10 Nov 2026

The initial [model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75), [dataset/evidence bundle](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75), [collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08), and [recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html) are public. Team submission source is [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon). The HF Article and final hackathon form remain unpublished/unsubmitted. `PUBLICATION-RESULTS.json` records the initial publication chronology, immutable revisions, verification results, and remaining blockers; the checkboxes below retain the preparation/final-approval gates and do not imply that these public artifacts are absent.

## Submission and freeze

- [ ] Confirm primary **Track 2a #2**: labelled/scored benchmark, dataset + report, adapter, evaluation logs, and demo; CuratorKIT→SafeTune→AuditKIT are load-bearing for source-model work.
- [ ] Preserve the custom-scorer boundary: merged interpolation/current MPS dev/frozen, Issue10, Arabic, and native-resolution metrics are custom contract-v2/native scorer results, not AuditKIT evaluations.
- [ ] Declare artifact freeze for **14 Nov 2026 at 23:59 AoE (UTC-12; 15 Nov 2026 at 11:59 UTC)**. Record final commit and artifact hashes before submission.
- [ ] Submit before the same deadline; retain confirmation locally. Do not alter frozen model/data afterward without explicitly declaring a new version.

## GitHub reproducibility README

- [ ] Lead with merged alpha=0.75, not historical v6; include adapter hash and Tiny Aya/Cohere Labs attribution.
- [ ] Document MIT for original code using `LICENSE`; do not apply MIT to Lexsi code, adapter weights, datasets, or prompts.
- [ ] Document the unrecovered original selection-code hash `d365ae53…` versus later frozen-support code `8ee0ae76…` and the subsequent cache fix. Do not promise byte-exact original selection-code regeneration.
- [ ] Make `release/replay_evidence.py` the saved-evidence verification path; publish its lock and custom scorers.
- [ ] Require a **fresh output root** for every authorized new generation. Never overwrite stored raw artifacts or train/tune on frozen cases.
- [ ] Include exact offline test commands and counts, environment/backend boundaries, and no-paid-job instructions.
- [ ] Explain resolution denominators 38/50 versus 27/34 and state that raw-base→merged contract-v2 improvement is unmeasured.

## Hugging Face Article

- [ ] Use `HF-ARTICLE.md` as the current-model handoff and `ABSTRACT.md` for the short summary.
- [ ] Include strongest merged results, negative results, custom-scorer scope, chronology, raw-base limitation, and backend separation.
- [ ] Link the final public repository, model collection, dataset collection, and demo only after their URLs exist and have been checked.
- [ ] Keep CircuitKIT explicitly historical-v6 smoke only.

## Public ungated model collection

- [ ] Review `.public_staging/evidencetune-merged-alpha-0.75/model_collection/` and its manifest/hashes.
- [ ] Include the actual merged adapter with completed `README.md` at adapter root, `license: cc-by-nc-4.0`, config, provenance, and `LICENSE-MODEL`.
- [ ] Include same-run baselines, raw outputs, run plans, native-resolution records, scorers, logs, and immutable v7/v8 source-adapter references.
- [ ] Ensure model files are publicly accessible and **ungated** after the user approves upload; do not create a collection in this task.
- [ ] Verify adapter SHA-256 `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335` after upload.

## Public ungated dataset collection

- [ ] Review `dataset_collection/` source rows, sidecar labels, freezes/manifests, curated v7/v8 training inputs, and dataset card.
- [ ] Preserve ContractNLI CC BY 4.0, VitaminC CC BY-SA 3.0, AraStance CC BY 4.0, and applicable share-alike/attribution obligations.
- [ ] Mark AI/synthetic labels as proxies and Issue #12 as `independent_ai_review` pending humans.
- [ ] Exclude rejected natural SciFact training packs and any unresolved/private data.
- [ ] Ensure dataset files are publicly accessible and **ungated** after approval; do not create a collection here.

## Demo and public-link checks

- [ ] Integrate `demo_merged_data.json` using `MERGED-DEMO.md`; keep historical v6 `demo.html`/`demo_data.json` separate.
- [ ] Verify exact demo regeneration and all four frozen raw-prediction hashes.
- [ ] Show recorded-only status, Apple MPS bf16 backend, synthetic/proxy labels, and no broad human/natural-domain claim.
- [ ] Check repository, Article, model/dataset collections, model files, dataset files, and demo links in a logged-out browser.
- [ ] Confirm no gates, authentication requirements, placeholder URLs, broken anchors, or public references to Korean raw rows.

## Raw evidence and integrity

- [ ] Verify `.release/` remains raw-free and uses the curated-file allowlist.
- [ ] Verify `.public_staging/` includes source/label packs, run plans, raw outputs, scorers, logs, curated training inputs, same-run baselines, and immutable source-adapter references.
- [ ] Run raw-record replay, release verification, public-staging verification, adapter hash comparison, and all tests.
- [ ] Confirm stored raw artifacts were not altered; derived English/Italian XSTest files preserve kept JSONL row bytes and have derivation records.

## Licensing and compliance

- [ ] Original project code: **MIT**, copyright `2026 EvidenceTune contributors`, explicitly selected by the user.
- [ ] Adapter: **CC BY-NC 4.0**, separate from MIT code.
- [ ] Licensed English XSTest and dataset-card-declared Italian XSTest-IT notices included.
- [ ] **Korean XSTest raw prompts, responses, source rows, and review rows excluded** unless license/permission is resolved.
- [ ] Applicable Lexsi LSAL v1.1/v1.2 license texts and modification notices included; no Lexsi code relicensed under MIT.
- [ ] Scan for credentials, environment files, private keys, unresolved/private material, and accidental vendor/cache uploads.

## Final human approval gates

- [ ] User approves exact public files, links, licenses, and submission text.
- [ ] User or authorized operator performs all public actions and external submissions.
- [ ] Record what was published, final URLs, immutable hashes, and the freeze declaration. No automated public action is part of this checklist.
