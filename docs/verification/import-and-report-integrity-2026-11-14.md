# Import and report integrity — 14 Nov 2026

These local fixes build on reviewed PRs #34 and #35. They do not change model weights, recorded data, annotations, or existing scores.

## Fixes

- `scripts/import_final_run.py`: verifies each policy's prediction list, row count and corresponding prompt/source-input identity immediately after loading, before creating or writing output. Swapped, truncated, extended, missing-prompt and non-string-prompt inputs fail with file/index/count diagnostics. It also rejects duplicate fresh `(case, condition)` groups, reporting both source indices rather than silently overwriting a prior row. Existing output bytes remain unchanged on rejection. The docstring now treats `fresh` as a historical source flag rather than a guarantee of no prior use.
- `scripts/check_benchmark.py`: fails repeated `case_id` values within or across splits and reports the ID and split counts. It does not silently deduplicate cases or modify source data.
- `scripts/annotation_agreement.py`: rejects duplicate logical identities in both CSV and JSONL before writing reports, including identical duplicates. The CLI prints an actionable error rather than calculating arbitrary last-row-wins agreement. Clean-input `load()` signatures and result shapes are unchanged.

## Fresh coordinator verification

Using the declared clean virtual environment, not a system interpreter missing dependencies:

- **200 tests passed in the final integrated rerun**: 187 Python tests across ten suites plus 13 Node tests, with no test skips. The Python suites cover scripts (58), teacher fake-client guards (22), release (13), demo with explicit raw evidence (6), presentation (4), uncertainty (11), raw-base analysis (10), staging/additive uploads (18), synthetic CPU tensor interpolation (8), and annotation compatibility (37).
- The 58 script tests include **11 importer and 8 duplicate-identity regressions**. This rerun does not include a new Chrome run; absent merged-renderer browser coverage remains explicitly skipped, not a browser pass.
- Four positive validator commands returned `OK` in two consecutive rounds: default, mock-smoke, final-fresh, and standalone schema examples.
- Read-only actual-data compatibility: `check_alignment` accepted all **1,020 saved historical source rows per policy** against the original v5 and v6 AuditKIT records. The 680 fresh `(case, condition)` groups are unique. Hashes of the input files matched before/after. The importer `main()` was not called and no recorded demo bundle was regenerated.
- `git diff --check` passed.

Each fix workflow independently reproduced failing synthetic controls before implementation. Its read-only reviewer approved the scoped code; their missing-jsonschema limitation was resolved by the coordinator's fresh full-suite rerun in the declared environment. Synthetic benchmark runs use temporary copies and cannot overwrite recorded checks.

Two bounded final sweeps found no further actionable failures on normal documented paths; the loop can switch to quiet state checks instead of spawning unchanged audits.

## Limits and verification incidents

Prompt substring alignment is an identity guard, not cryptographic proof of model provenance or output correctness. A legitimately rewritten prompt fails loudly rather than being silently paired. Unknown annotation-ID warnings are unchanged. No model, teacher, human audit, training, inference, or network download was needed for these tests.

One implementer reported an unexplained earlier `--cases` result. The exact invocation was not preserved in that report; all four prescribed coordinator commands passed twice. No claim is made about the cause of that earlier invocation.

A final read-only sweep incorrectly invoked the benchmark checker once against the actual worktree before switching to a temporary copy. That regenerated `data/benchmark/checks.json` with an added empty duplicate-ID field; the reviewer restored it. The coordinator independently verified its blob hash exactly equals the pre-fix version, and confirmed no committed differences in data, schemas, recorded demo data, annotation references or kits. No recorded-data changes are included. Future mutating checker runs must use temporary roots only. This incident is not counted as an actual-data rewrite performed by the importer.
