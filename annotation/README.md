# Blind human double-annotation kit

Start with **[ANNOTATION-GUIDE.md](ANNOTATION-GUIDE.md)**. Current completion state is in **[ANNOTATION-STATUS.md](ANNOTATION-STATUS.md)**.

## Default pilot

- `pilot/annotate.html` — self-contained offline UI; open directly in a browser.
- `pilot/items.json` — 40 blind source rows from 40 non-fresh cases, one stratified condition per case; no model outputs or proxy-label fields.
- `pilot/assignment_a.json`, `pilot/assignment_b.json` — same row universe, different deterministic order.
- `pilot/manifest.json` — counts, frozen-input hashes, blinding boundary, and artifact hashes.

Two humans independently complete A and B. The coordinator then runs `agreement.py`, prepares human adjudication with `adjudicate.py prepare`, and merges validated decisions with `adjudicate.py merge`.

## Tools

- `build_kit.py` — verifies the frozen source hashes and deterministically writes the non-fresh pilot under `evidencetune.task.v2`. Fresh export requires separate explicit flags.
- `annotation_lib.py` — blind-item parsing, strict export validation, agreement metrics, adjudication queue/template, and merge logic.
- `agreement.py` — observed agreement, Cohen’s kappa, confusion matrices, action-set agreement, and Jaccard similarity.
- `adjudicate.py` — conflict-only human adjudication and validated consensus/conflict merge.
- `ui_template.html` — offline HTML/CSS/JavaScript source for the generated UI.
- `tests/test_annotation_kit.py` — synthetic unit and end-to-end CLI tests.

## Verify locally

Run from the repository root (`data_final/` must be present; it is not committed):

```bash
python3 -I annotation/build_kit.py --check-only
python3 -I -m unittest discover -s annotation/tests -v
```

No model, paid job, network service, package install, server, publishing step, or push is part of this kit. No files are written outside `annotation/`; CLI output paths are confined there. All input/output and output/output collisions are rejected, and existing outputs require explicit `--overwrite`.

## Template benchmark v1 (separate set)

The 60-family fictional-source benchmark under `data/families/` has its own blind sheets and QA pass: see [BENCHMARK-V1.md](BENCHMARK-V1.md).
