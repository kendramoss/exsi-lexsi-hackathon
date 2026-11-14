# Import and report integrity — 14 Nov 2026

These local fixes build on reviewed PRs #34 and #35. They do not change model weights, recorded data, annotations, or existing scores.

## Fixes

- `scripts/import_final_run.py`: verifies each policy's prediction list, row count and corresponding prompt/source-input identity immediately after loading, before creating or writing output. Swapped, truncated, extended, missing-prompt and non-string-prompt inputs fail with file/index/count diagnostics. Existing output bytes remain unchanged on rejection. The docstring now treats `fresh` as a historical source flag rather than a guarantee of no prior use.
- `scripts/check_benchmark.py`: fails repeated `case_id` values within or across splits and reports the ID and split counts. It does not silently deduplicate cases or modify source data.
- `scripts/annotation_agreement.py`: rejects duplicate logical identities in both CSV and JSONL before writing reports, including identical duplicates. The CLI prints an actionable error rather than calculating arbitrary last-row-wins agreement. Clean-input `load()` signatures and result shapes are unchanged.

## Fresh coordinator verification

Using the declared clean virtual environment, not a system interpreter missing dependencies:

- **55 script tests passed**, including the new 8 importer and 8 duplicate-identity regressions.
- **37 annotation tests passed**.
- Four positive validator commands returned `OK`: default, mock-smoke, final-fresh, and standalone schema examples.
- Read-only actual-data compatibility: `check_alignment` accepted all **1,020 saved historical source rows per policy** against the original v5 and v6 AuditKIT records. Hashes of all three input files matched before/after. The importer `main()` was not called and no recorded bundle was regenerated.
- `git diff --check` passed.

Each fix workflow independently reproduced failing synthetic controls before implementation. Its read-only reviewer approved the scoped code; their missing-jsonschema limitation was resolved by the coordinator's fresh full-suite rerun in the declared environment. Synthetic benchmark runs use temporary copies and cannot overwrite recorded checks.

## Limits

Prompt substring alignment is an identity guard, not cryptographic proof of model provenance or output correctness. A legitimately rewritten prompt fails loudly rather than being silently paired. Unknown annotation-ID warnings are unchanged. No model, teacher, human audit, training, inference, or network download was needed for these tests.
