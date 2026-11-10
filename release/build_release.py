#!/usr/bin/env python3
"""Build the ignored local EvidenceTune alpha=0.75 release bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_release import EXPECTED_ADAPTER_SHA256, sha256_file, verify_release
from model_card import render_model_card


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
DEFAULT_OUTPUT = WORKTREE_ROOT / ".release/evidencetune-merge-alpha-0.75"

CURATED_RESULT_NAMES = (
    "AI-REVIEW-RESULTS.md", "CIRCUITKIT-SMOKE-RESULTS.md", "DPO-SELECTION.json",
    "ISSUE10-EVALUATION.json", "ISSUE11-OVERREFUSAL-RESULTS.md",
    "ISSUE8-ARABIC-EVALUATION.json", "MERGE-RESULTS.md", "NATURAL-DATA-RESULTS.md",
    "V7-RESULTS.md", "V8-RESULTS.md", "frozen_summary.json", "frozen_validation.json",
    "local_validation.json", "selection.json",
)
CURATED_SOURCE_NAMES = (
    "README.md", "merge_eval/evaluation_plan.json", "merge_eval/frozen_confirm.py",
    "merge_eval/local_eval.py", "merge_eval/merge_lora.py",
    "merge_eval/tests/test_local_eval.py", "merge_eval/tests/test_merge_lora.py",
    "scorers/__init__.py", "scorers/contract_v2.py", "scorers/resolution_replay.py",
)
CURATED_COPY_MAP = {
    "release/README.md": "README.md",
    "release/REPRODUCE.md": "REPRODUCE.md",
    "release/MODEL_CARD.md": "MODEL_CARD.md",
    "release/replay_evidence.py": "replay_evidence.py",
    "release/model_card.py": "model_card.py",
    "release/evidence-lock.json": "evidence-lock.json",
    "LICENSE": "LICENSE",
    "LICENSE-DECISION.md": "LICENSE-DECISION.md",
    "LICENSE-MODEL": "LICENSE-MODEL",
    "NOTICE.md": "NOTICE.md",
    **{f"results/merged/{name}": f"results/{name}" for name in CURATED_RESULT_NAMES},
    **{f"release/source/{name}": f"source/{name}" for name in CURATED_SOURCE_NAMES},
}


def is_curated_release_path(relative: str) -> bool:
    return relative in CURATED_COPY_MAP


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def build_release(worktree_root: Path, raw_root: Path, output: Path) -> dict:
    """Copy only curated evidence and source files; never include raw predictions."""
    worktree_root = Path(worktree_root)
    raw_root = Path(raw_root)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing release: {output}")
    source_adapter = raw_root / "merge_eval/adapters/alpha_0.75"
    if sha256_file(source_adapter / "adapter_model.safetensors") != EXPECTED_ADAPTER_SHA256:
        raise ValueError("source adapter differs from the selected merged adapter")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        for name in ("adapter_model.safetensors", "adapter_config.json", "merge_provenance.json"):
            copy_file(source_adapter / name, temporary / "adapter" / name)
        (temporary / "adapter/README.md").write_text(
            render_model_card(worktree_root, "adapter_root"), encoding="utf-8"
        )
        for relative, destination in sorted(CURATED_COPY_MAP.items()):
            copy_file(worktree_root / relative, temporary / destination)

        files = []
        for path in sorted(temporary.rglob("*")):
            if path.is_file():
                files.append({
                    "path": path.relative_to(temporary).as_posix(),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                })
        manifest = {
            "schema_version": 1,
            "release_id": "evidencetune-merge-alpha-0.75-local-2026-11-10",
            "base_model": "CohereLabs/tiny-aya-global",
            "model": "merge_alpha_0.75",
            "formula": "0.75 * v7 + 0.25 * v8",
            "adapter_sha256": EXPECTED_ADAPTER_SHA256,
            "backend": "local Apple MPS bf16 Transformers; frozen confirmation only",
            "label_scope": "contract-v2 synthetic/proxy; no human or broad natural-domain validation",
            "raw_predictions_included": False,
            "files": files,
        }
        write_json(temporary / "manifest.json", manifest)
        sums = [f"{entry['sha256']}  {entry['path']}" for entry in files]
        sums.append(f"{sha256_file(temporary / 'manifest.json')}  manifest.json")
        (temporary / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        verify_release(temporary)
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree-root", type=Path, default=WORKTREE_ROOT)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    manifest = build_release(arguments.worktree_root, arguments.raw_root, arguments.output)
    print(json.dumps({
        "status": "PASS",
        "output": str(arguments.output),
        "payload_files": len(manifest["files"]),
        "adapter_sha256": manifest["adapter_sha256"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
