# Offline development checks

These checks validate tracked data, recorded demo payloads, and tiny synthetic
CPU tensors. They do not run model inference, training, teacher labelling, or
external services. They do not change the selected merged alpha=0.75 model or
establish human validation of teacher labels.

## Lightweight environment

From the repository root, use Python 3.10 or newer. Create an environment with
whichever Python command your system provides (`python3`, `python`, or `py -3`):

```sh
python3 -m venv .venv
```

Use that environment's interpreter directly; activation is optional:

| System | Environment interpreter (replace `python` below with this) |
| --- | --- |
| macOS / Linux | `.venv/bin/python` |
| Windows | `.venv\Scripts\python.exe` |

On a connected machine, `python -m pip install -r requirements-dev.txt` installs
`jsonschema` for schemas, `PyYAML` for staging/card metadata, and `numpy` plus
`safetensors` for synthetic tensor checks. No Torch, Transformers, training SDK,
or GPU package is required by these checks. The file specifies minimum versions,
not a reproducible lockfile.

For an air-gapped machine, prepare a wheel directory on a connected machine with
a compatible OS, architecture, and Python version. Include transitive dependencies:

```sh
python -m pip download --only-binary=:all: --dest wheelhouse -r requirements-dev.txt
```

Transfer the wheel directory and checkout, then install without network access:

```sh
python -m pip install --no-index --find-links=wheelhouse -r requirements-dev.txt
python -c "import jsonschema, yaml, numpy, safetensors; print('offline dependencies import OK')"
```

A suitable local wheel directory is a prerequisite, not something supplied by
this repository.

### Clean-install record

Verified at commit d06b6ec in a fresh venv created without system site packages
(`python -m venv .venv-offline-verify`, git-ignored) from Anaconda Python 3.13.9
on macOS arm64, with `python -m pip install -r requirements-dev.txt` from the
standard package index. Resolved versions: jsonschema 4.26.0, PyYAML 6.0.3,
numpy 2.5.4, safetensors 0.8.0 (plus attrs 26.1.0, jsonschema-specifications
2025.9.1, referencing 0.37.0, rpds-py 2026.9.1), with pip 25.2. This is one
resolution on one platform, not a lockfile; minimum-version combinations and
Windows/Linux were not tested, and no wheelhouse/air-gapped install was run.

All commands below passed in that venv: the four `validate.py` runs;
`scripts/tests` 35 tests (before adding the clean-environment guard tests);
`demo/tests` 6 tests with 2 explicit SKIPs (raw integration,
`EVTUNE_DEMO_RAW_ROOT` unset); `teacher/tests` 22 tests (fake client);
merge-LoRA synthetic tensor tests 8; `public_staging/tests` 14; Node
`merged-data.test.cjs` 4 pass. No raw-replay or build checks were run (no
evidence roots supplied) and no inference was run.

## Checks requiring only this checkout

Run from the repository root using the environment interpreter:

```sh
python -I -B scripts/validate.py
python -I -B scripts/validate.py demo/data/results/mock-smoke
python -I -B scripts/validate.py demo/data/results/final-fresh
python -I -B scripts/validate.py --cases schemas/examples/cases.example.jsonl
python -I -B -m unittest discover -s scripts/tests -v
python -I -B -m unittest discover -s demo/tests -v
python -I -B -m unittest discover -s teacher/tests -v
python -I -B -m unittest discover -s public_staging/tests -v
python -I -B -m unittest discover -s release/source/merge_eval/tests -p test_merge_lora.py -v
node --test demo/tests/merged-data.test.cjs
```

The Node checks use built-in modules only (Node 22 tested); no npm installation is
needed. The tensor tests create tiny synthetic adapters, not copies of released
weights. Set `TMPDIR` (POSIX) or `TEMP` (Windows) to an existing scratch directory
when needed; older tensor tests explicitly place their scratch folders beside
their test file, so they also require a writable checkout.

Completed-run validation requires all of `cases.jsonl`, `predictions.jsonl`, and
`metrics.json`. Case IDs, comparator IDs, and case/policy pairs must be unique;
`dataset.n_cases` must equal the case row count, and each declared comparator
must have exactly one prediction for every case. Empty predictions are not a
completed run. `--cases` remains a standalone schema-only export check, with no
completed-run prerequisites. The merged-model `merged.json` payload is a separate
format checked by the demo tests, not by this three-file validator.

## Explicit raw-evidence demo integration

Without `EVTUNE_DEMO_RAW_ROOT`, the four payload-only demo checks run from tracked
`demo_merged_data.json`; the two raw regeneration/hash checks report **SKIP**.
The test-mode regressions also verify that default skipping is explicit and that
requesting missing evidence fails. A passing default run is not raw-source
regeneration or an adapter integrity attestation.

To run both raw integration checks, set `EVTUNE_DEMO_RAW_ROOT` to your own evidence
directory, then repeat the same demo test command:

```sh
# POSIX shell
export EVTUNE_DEMO_RAW_ROOT="/path/to/your/evtune"
python -I -B -m unittest discover -s demo/tests -p test_merged_demo.py -v
```

```powershell
# Windows PowerShell
$env:EVTUNE_DEMO_RAW_ROOT = "C:\path\to\your\evtune"
.venv\Scripts\python.exe -I -B -m unittest discover -s demo/tests -p test_merged_demo.py -v
```

Explicit evidence mode fails rather than skips for an empty setting, missing
inputs, or incorrect frozen hashes. Required inputs under that root are:

- `merge_eval/local_results/evaluation/selection.json`
- `merge_eval/local_results/frozen_confirmation/frozen_summary.json`
- `merge_eval/adapters/alpha_0.75/adapter_model.safetensors`
- `merge_eval/local_results/frozen_confirmation/evaluation/{baseline_v7,merge_alpha_0.75}/{semantic_frozen_test,v8_targeted_frozen_test}/raw_predictions.json` (four files)
- `semantic_contrast/packs_v2/frozen_test_source.jsonl`
- `semantic_contrast/packs_v2/frozen_test_labels.json`

The integration checks retain exact saved-prediction regeneration, equality with
the tracked payload, and all four raw-input hash-before-JSON tamper checks. They
read the adapter to check its locked hash but do not run it or copy its weights.
Unset the variable to return to checkout-only checks.

Full release, raw replay, staging, and some local-evaluation integration tests
have additional private/local evidence prerequisites and may still use historical
author paths. Installing the lightweight dependencies does not supply those
artifacts or make those full suites portable. Do not interpret their omission
from the checkout-only commands as verified integration coverage.
