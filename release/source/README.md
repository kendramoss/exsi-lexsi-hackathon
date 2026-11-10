# Merge and replay source provenance

The locked dev plan records original selection-code `local_eval.py` SHA-256 `d365ae53b563afaacc7ac7ba31ba0ea13fff3dc218e540a113df47c3bce3034f`. Those original bytes could not be recovered. The available frozen-support version used by the frozen plan has SHA-256 `8ee0ae766af877ba575be6b5e6cfd7d6905ca637fa57712d224f3d76621cfe1c`.

The `merge_eval/local_eval.py` in this directory is **later frozen-support/cache-fixed code**, not the original selection implementation. The cache fix validates the complete saved resolution summary against saved records before reuse. Historical hashes are not altered to disguise this drift.

- `merge_eval/merge_lora.py`: CPU-only LoRA interpolation and tensor validation.
- `merge_eval/local_eval.py`: later dev/frozen support with cached-resolution validation.
- `merge_eval/frozen_confirm.py`: locked two-arm frozen confirmation support.
- `merge_eval/evaluation_plan.json`: original experiment plan and input hashes.
- `merge_eval/tests/`: 17 original tests plus the new altered-cache regression.
- `scorers/contract_v2.py`: standalone custom contract-v2 scorer used by replay/demo.
- `scorers/resolution_replay.py`: record-derived native-resolution metric replay and cache comparison.

Use `release/replay_evidence.py` to reproduce selection/headline metrics from saved records. New generation, separately authorized, requires a fresh output root and a complete checkout with data, cached base model, and existing dependencies. These custom merged/MPS scorers are not AuditKIT; AuditKIT produced source-model evaluations.
