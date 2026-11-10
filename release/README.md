# Local EvidenceTune merged-model release

This directory contains the source and tooling for the merged-model release. The generated local package lives at `../.release/evidencetune-merge-alpha-0.75/`; `.release/` is ignored by Git. The verified public adapter is [Mizore66/evidencetune-merged-alpha-0.75](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75), and the team submission source is [kendramoss/exsi-lexsi-hackathon](https://github.com/kendramoss/exsi-lexsi-hackathon).

## Package contents

- `adapter/`: actual alpha=0.75 adapter tensor, config, completed CC BY-NC model card, and merge provenance.
- `MODEL_CARD.md`: intended use, exact results, negative results, and claim boundaries.
- `REPRODUCE.md`: offline verification and reproduction commands.
- `manifest.json` and `SHA256SUMS`: complete payload inventory and hashes.
- `results/`: curated merged-model summaries and follow-up evaluations, without raw prediction dumps.
- `source/merge_eval/`: interpolation and later frozen-support/cache-fixed code, plan, and 17 original tests plus altered-cache regression.
- `replay_evidence.py` + `evidence-lock.json`: raw-record selection/headline replay; original selection-code bytes are unavailable.
- `LICENSE`, `LICENSE-MODEL`, `NOTICE.md`: MIT original code, CC BY-NC adapter, and separate third-party notices.

The adapter is 120,981,200 bytes and is intentionally ignored by Git along with the rest of the generated bundle. The tracked files here rebuild the bundle when the verified raw adapter is available.

## Commands

Run from the submission worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I -m unittest discover -s release/tests -v
PYTHONDONTWRITEBYTECODE=1 /Users/anasqumhiyeh/lexsi-koth/tools/evtune-local-venv/bin/python -I release/verify_release.py .release/evidencetune-merge-alpha-0.75
```

Do not add raw predictions, generated batches, or response dumps to the bundle. Do not publish the package without explicit approval.
