# Reproduce and verify the local merged-model release

All steps are local. Do not train or tune on frozen cases, alter stored raw artifacts, publish packages, or launch paid jobs as part of verification.

## 1. Verify the raw-free adapter package

From the submission worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I release/verify_release.py .release/evidencetune-merge-alpha-0.75
```

The verifier checks the exact allowlisted inventory, every size and SHA-256, `SHA256SUMS`, the selected adapter, locked dev selection, confirmation-only frozen summary, Apple MPS bf16 backend, interpolation provenance, completed adapter-root model card, and recorded 1,020-record validation. Raw model records are forbidden even if renamed.

## 2. Replay selection and frozen metrics from saved records

This is the supported selection-evidence reproduction check:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I release/replay_evidence.py \
  --raw-root /Users/anasqumhiyeh/lexsi-koth/evtune
```

The stdlib validator verifies 55 locked inputs before parsing them, validates source/sidecar identities, rescores contract-v2 outputs, recomputes summaries and all selection gates, replays five native-resolution arms, and compares the frozen headline. It covers **3,120 single-turn records**, including the **1,020 frozen records**. It validates saved evidence, not fresh generation or missing source-code bytes.

Resolution replay reconstructs source cases, rescores every follow-up `raw_output` for terminal action, answer, excerpt references, and novel quoted spans, then recomputes every record-derived metric and compares the complete cached metrics object. Timing and aggregate token usage are not stored per record; those fields are carried from `resolution_raw.metrics` for comparison and cannot be independently reconstructed from records alone.

To replay directly from split public staging without changing staged bytes:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I -B .public_staging/evidencetune-merged-alpha-0.75/code/release/replay_evidence.py \
  --staging-root .public_staging/evidencetune-merged-alpha-0.75
```

This creates a temporary read-only symlink layout mapping model evidence and dataset packs to the expected raw paths, then removes it.

## 3. Selection-code provenance and source drift

The locked dev plan `merge_eval/local_results/plan.json` records original selection-code `local_eval_sha256` **`d365ae53b563afaacc7ac7ba31ba0ea13fff3dc218e540a113df47c3bce3034f`**. The available frozen-support script used by the frozen plan has SHA-256 **`8ee0ae766af877ba575be6b5e6cfd7d6905ca637fa57712d224f3d76621cfe1c`**. The original selection-code bytes could not be recovered.

The packaged `source/merge_eval/local_eval.py` is **later frozen-support/cache-fixed code**, not the original selection implementation. Its cached-resolution branch now recomputes and compares saved summary metrics against `resolution_raw.json` before reuse. Historical plan, selection, and frozen hashes are deliberately unchanged. Do not claim byte-exact original selection-code regeneration or use the later script hash as proof of the original run.

AuditKIT produced source-model evaluations. Merged interpolation and current MPS dev/frozen, Issue10, Arabic, and native-resolution evaluations used custom EvidenceTune contract-v2/native scorers. CircuitKIT is historical original-v6 smoke only.

## 4. Rebuild the raw-free package

The adapter is copied from the read-only raw experiment root; curated documents and source files come from an explicit worktree allowlist.

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I release/build_release.py \
  --raw-root /Users/anasqumhiyeh/lexsi-koth/evtune \
  --output .release/evidencetune-merge-alpha-0.75-new
```

The builder refuses to overwrite an existing bundle. Choose a fresh output path; never replace the source adapter.

## 5. Reproduce the adapter interpolation

Requirements for the merge script are Python, NumPy 2.3.5, and safetensors 0.8.0. Source v7/v8 paths and immutable hashes are in `adapter/merge_provenance.json`; the separate public staging includes their actual artifacts.

From a complete EvidenceTune checkout:

```bash
python -I merge_eval/merge_lora.py \
  --v7 results/v7/evtune-next-output/v6_semantic/adapter \
  --v8 results/v8/evtune-v8-output/v8_targeted_two_turn/adapter \
  --output-root /path/to/fresh-ignored-merge-output \
  --alphas 0.75
```

Expected output: `alpha_0.75/adapter_model.safetensors`, 120,981,200 bytes, SHA-256 `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`. This CPU-only interpolation performs no training or frozen evaluation.

## 6. New generation only with fresh output roots

No generation is needed for submission verification. If separately authorized, use a complete checkout and **fresh, nonexisting output roots** so cached/raw artifacts remain untouched:

```bash
python -I merge_eval/local_eval.py --output-root /path/to/fresh-dev-output
python -I merge_eval/frozen_confirm.py --output-root /path/to/fresh-frozen-output
```

Do not run these commands against the historical `local_results/` directory. Selection must remain dev-only and lock before any new two-arm merged confirmation. **No new two-arm merged-confirmation generation occurred before `selection.json` was locked. Earlier v7/v8 frozen runs existed but were not used for merged-model selection.**

The later scripts require the full source/data tree, cached Tiny Aya model, Apple MPS, PyTorch, Transformers, PEFT, and existing dependencies. The original 17 merge tests plus the new altered-cache regression are included under `source/merge_eval/tests/`.

## 7. Regenerate and verify the curated demo

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I demo/build_merged_demo.py \
  --raw-root /Users/anasqumhiyeh/lexsi-koth/evtune \
  --output demo_merged_data.json
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I demo/build_merged_demo.py \
  --raw-root /Users/anasqumhiyeh/lexsi-koth/evtune \
  --output demo_merged_data.json --verify
```

All four frozen raw-prediction inputs are hash-checked before JSON loading. Illustrated outputs are rescored against the semantic frozen sidecars. The payload uses the first complete semantic frozen case in saved order and same-backend v7/merged scoreboards. Raw predictions remain outside Git and the raw-free release.

## 8. Build and verify complete local public staging

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I public_staging/build_staging.py
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I public_staging/build_staging.py \
  --output .public_staging/evidencetune-merged-alpha-0.75 --verify
```

This separate ignored tree includes source/label packs, curated training inputs, run plans, raw outputs, scorers, logs, same-run baselines, and immutable source-adapter references. Korean XSTest raw rows, credentials, unresolved/private files, and rejected natural packs are excluded. Running the builder performs no public action. The existing public artifacts are the [model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75), [dataset/evidence bundle](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75), and [collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08).

## 9. Raw-base and paired-uncertainty evidence (offline, post-selection)

Both analyses read the saved frozen predictions and do not train, tune, reselect, or generate with the public model.

```bash
PY=/Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python
PYTHONDONTWRITEBYTECODE=1 "$PY" -I -m unittest discover -s analysis -p "test_paired_uncertainty.py" -v
PYTHONDONTWRITEBYTECODE=1 "$PY" -I -m unittest discover -s analysis/raw_base/tests -v
```

`analysis/paired_uncertainty.py` regenerates `UNCERTAINTY.md` and `results/merged/uncertainty/` byte-for-byte from the saved merged and v7 records (10,000 case-cluster bootstrap replications, seed 20261111). The raw-base predictions (`BASE-EVALUATION.md`) were generated once on local Apple MPS bf16 with an unadapted `CohereLabs/tiny-aya-global` (commit `af89d219b53ed9b13b8a4645f9c8028973510324`); regenerating them requires the cached base model and a fresh output root, and is not part of verification. The raw-base predictions are public additive evidence under `evidence/raw_base/`; the aggregate summary is `results/merged/raw_base/summary.json`. The saved v7 and merged predictions were not regenerated, and their historical Python/Transformers versions are not pinned, so the raw-base comparison is descriptive, not a same-run experiment.

## Evidence and license boundaries

All contract-v2 labels are synthetic/proxy. AI review is not human validation; Issue #12 remains `independent_ai_review`. DPO and natural SciFact training are rejected. Contradiction and Arabic weaknesses remain. A post-selection raw-base arm was evaluated on the same suites/backend; it is descriptive only. See `BASE-EVALUATION.md` and `UNCERTAINTY.md`. Resolution rates 38/50 and 27/34 are conditional on different CLARIFY follow-up denominators.

Original EvidenceTune code is MIT licensed. The adapter is CC BY-NC 4.0. Dataset licenses and Lexsi LSAL notices remain separate; see `LICENSE-DECISION.md` and `NOTICE.md`.
