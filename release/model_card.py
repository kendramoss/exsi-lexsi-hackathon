"""Render the canonical model card with installation-context-correct relative paths."""
from __future__ import annotations

from pathlib import Path


def render_model_card(worktree_root: Path, context: str) -> str:
    text = (Path(worktree_root) / "release/MODEL_CARD.md").read_text(encoding="utf-8")
    if context == "release_root":
        return text
    if context == "adapter_root":
        replacements = {
            "adapter/adapter_model.safetensors": "adapter_model.safetensors",
            "](REPRODUCE.md)": "](../REPRODUCE.md)",
            "](SHA256SUMS)": "](../SHA256SUMS)",
            "](manifest.json)": "](../manifest.json)",
            "](adapter/merge_provenance.json)": "](merge_provenance.json)",
            "](results/)": "](../results/)",
            "`LICENSE-MODEL`": "`../LICENSE-MODEL`",
        }
    elif context == "model_collection":
        replacements = {
            "adapter/adapter_model.safetensors": "adapter_model.safetensors",
            "](REPRODUCE.md)": "](code/release/REPRODUCE.md)",
            "](SHA256SUMS)": "](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75/blob/main/SHA256SUMS)",
            "](manifest.json)": "](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75/blob/main/manifest.json)",
            "](adapter/merge_provenance.json)": "](merge_provenance.json)",
            "](results/)": "](evidence/)",
        }
    else:
        raise ValueError(f"unknown model-card context: {context}")
    for old, new in replacements.items():
        text = text.replace(old, new)
    if context == "model_collection":
        text = text.replace(
            "Raw prediction files are deliberately excluded from this release; aggregate summaries and the separately curated demo payload retain the evidence pointers and hashes.",
            "Raw prediction files, native-resolution records, source-model AuditKIT outputs, and custom-scored evidence are retained under `evidence/` with plans, logs, summaries, and hashes.",
        )
    return text
