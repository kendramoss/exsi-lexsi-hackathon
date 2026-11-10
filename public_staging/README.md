# Local public-artifact staging

This builder creates a complete local staging tree at `.public_staging/evidencetune-merged-alpha-0.75/` for the merged-model public artifacts. It does not create or update Hugging Face repositories or collections. The verified live artifacts are the [model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75), [dataset/evidence bundle](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75), [collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08), and [recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html).

- `model_collection/`: merged adapter, completed CC BY-NC model card, same-run baselines, immutable merge inputs, raw outputs, run plans, logs, scorers, and summaries.
- `dataset_collection/`: source/label packs, freeze records, curated v7/v8 training inputs, dataset card, and English/Italian-only derived XSTest prompts.
- `code/`: original EvidenceTune code and custom contract-v2/native scorers.
- `third_party/Lexsi/`: applicable LSAL license texts; Lexsi source trees are not vendored.
- `manifest.json`, `SOURCE-MAP.json`, `SHA256SUMS`: portable relative paths, source mapping, sizes, and hashes.

Original code is MIT licensed. Adapter weights are CC BY-NC 4.0. Dataset and Lexsi terms are separate. Korean XSTest raw rows and credential/private material are forbidden.

```bash
PY=/Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python
PYTHONDONTWRITEBYTECODE=1 "$PY" -I public_staging/build_staging.py
PYTHONDONTWRITEBYTECODE=1 "$PY" -I public_staging/build_staging.py \
  --output .public_staging/evidencetune-merged-alpha-0.75 --verify
```

The builder refuses to overwrite an existing staging tree. Raw source files are never edited. Derived English/Italian JSONL files preserve every kept row's original bytes and include derivation/hashes. Historical files may retain absolute experiment paths for audit; the new manifest and source map are relative and portable.
