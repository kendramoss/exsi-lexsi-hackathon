#!/usr/bin/env python3
"""Build a small, additive upload directory for the public model repository.

The directory contains ONLY an explicit allowlist: the two updated cards, new raw-base and
uncertainty evidence, and a regenerated ``manifest.json`` / ``SHA256SUMS`` that list every file
that will exist in the repository after upload (previously published files keep the exact
hashes recorded in the pinned live manifest; nothing already published is removed or altered
except the two cards that are intentionally updated).

Nothing here talks to the network or uploads. Uploading is a separate, reviewed step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKTREE_ROOT / "release"))
from model_card import render_model_card  # noqa: E402

BASE_EVAL_RUN = Path("/Users/anasqumhiyeh/.claude/worktrees/exsi-base-eval/.base_eval")
RAW_BASE_PREDICTIONS = {
    "semantic_frozen_test": "65b69be04e96f802f10eca62ed14b38789194bfd8fa85c6df2b4a9e3735fa971",
    "v8_targeted_frozen_test": "922aa25794b7b1c63574a744a4bbadbeaa4c5a68f6e27e836b3c770ddd625a6d",
}
UPDATED_CARDS = ("README.md", "code/release/REPRODUCE.md")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def allowlist(worktree_root: Path, base_eval_run: Path) -> dict[str, Path | bytes]:
    """Map upload-relative destination -> source path (or rendered bytes)."""
    w, b = Path(worktree_root), Path(base_eval_run)
    items: dict[str, Path | bytes] = {
        "README.md": render_model_card(w, "model_collection").encode("utf-8"),
        "code/release/REPRODUCE.md": w / "release/REPRODUCE.md",
        "evidence/raw_base/BASE-EVALUATION.md": w / "BASE-EVALUATION.md",
        "evidence/raw_base/summary.json": w / "results/merged/raw_base/summary.json",
        "evidence/raw_base/run_plan.md": w / "results/merged/raw_base/run_plan.md",
        "evidence/raw_base/artifact_inventory.json": w / "results/merged/raw_base/artifact_inventory.json",
        "evidence/raw_base/provenance.json": w / "results/merged/raw_base/provenance.json",
        "evidence/raw_base/environment.txt": w / "results/merged/raw_base/environment.txt",
        "evidence/raw_base/logs/runtime.json": w / "results/merged/raw_base/runtime.json",
        "evidence/raw_base/code/base_eval.py": w / "analysis/raw_base/base_eval.py",
        "evidence/raw_base/code/generation_base_eval.py": w / "analysis/raw_base/generation_base_eval.py",
        "evidence/raw_base/code/tests/test_base_eval.py": w / "analysis/raw_base/tests/test_base_eval.py",
        "evidence/uncertainty/UNCERTAINTY.md": w / "UNCERTAINTY.md",
        "evidence/uncertainty/paired_results.json": w / "results/merged/uncertainty/paired_results.json",
        "evidence/uncertainty/input_hashes.json": w / "results/merged/uncertainty/input_hashes.json",
        "evidence/uncertainty/provenance.json": w / "results/merged/uncertainty/provenance.json",
        "evidence/uncertainty/code/paired_uncertainty.py": w / "analysis/paired_uncertainty.py",
        "evidence/uncertainty/code/test_paired_uncertainty.py": w / "analysis/test_paired_uncertainty.py",
    }
    for view in RAW_BASE_PREDICTIONS:
        items[f"evidence/raw_base/predictions/{view}/raw_predictions.json"] = (
            b / f"predictions/evaluation/raw_base/{view}/raw_predictions.json"
        )
    return items


def build_upload(worktree_root: Path, base_eval_run: Path, live_manifest: Path, live_revision: str,
                 output: Path) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    live = json.loads(Path(live_manifest).read_text(encoding="utf-8"))
    if live.get("collection") != "model_collection" or live.get("schema_version") != 1:
        raise ValueError("unexpected live manifest")
    published = {entry["path"]: entry for entry in live["files"]}
    items = allowlist(worktree_root, base_eval_run)

    for view, expected in RAW_BASE_PREDICTIONS.items():
        source = items[f"evidence/raw_base/predictions/{view}/raw_predictions.json"]
        if sha256_file(source) != expected:
            raise ValueError(f"raw-base prediction hash mismatch: {view}")
    for destination in items:
        if destination in published and destination not in UPDATED_CARDS:
            raise ValueError(f"allowlist would overwrite a published file: {destination}")
    for card in UPDATED_CARDS:
        if card not in published:
            raise ValueError(f"expected published card missing from live manifest: {card}")

    output.mkdir(parents=True)
    new_entries = {}
    try:
        for destination, source in sorted(items.items()):
            target = output / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(source, bytes):
                target.write_bytes(source)
            else:
                if not source.is_file() or source.is_symlink():
                    raise FileNotFoundError(source)
                shutil.copyfile(source, target)
            text_like = target.suffix in {".md", ".json", ".py", ".txt"}
            if text_like:
                body = target.read_text(encoding="utf-8")
                if "hf_" in body and any(
                    len(token) >= 33 and token.startswith("hf_") and token[3:].isalnum()
                    for token in body.replace('"', " ").split()
                ):
                    raise ValueError(f"credential-like content in {destination}")
            new_entries[destination] = {
                "path": destination,
                "sha256": sha256_file(target),
                "size_bytes": target.stat().st_size,
            }

        merged = dict(published)
        merged.update(new_entries)
        files = [merged[path] for path in sorted(merged)]
        manifest = {"collection": "model_collection", "files": files, "schema_version": 1}
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (output / "manifest.json").write_bytes(manifest_bytes)
        sums = [f"{entry['sha256']}  {entry['path']}" for entry in files]
        sums.append(f"{sha256_bytes(manifest_bytes)}  manifest.json")
        (output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {
        "live_revision": live_revision,
        "upload_files": sorted([*items, "manifest.json", "SHA256SUMS"]),
        "updated_published_files": sorted(set(items) & set(published)) + ["manifest.json", "SHA256SUMS"],
        "new_files": sorted(set(items) - set(published)),
        "manifest_files_after_upload": len(files),
    }


def verify_upload(output: Path, live_manifest: Path) -> dict:
    """Check the upload directory is exactly the allowlist and the manifest is self-consistent."""
    output = Path(output)
    live = json.loads(Path(live_manifest).read_text(encoding="utf-8"))
    published = {entry["path"]: entry for entry in live["files"]}
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    declared = {entry["path"]: entry for entry in manifest["files"]}
    present = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    uploaded = present - {"manifest.json", "SHA256SUMS"}
    if not uploaded <= set(declared):
        raise ValueError("uploaded file missing from manifest")
    for path in uploaded:
        entry = declared[path]
        if sha256_file(output / path) != entry["sha256"] or (output / path).stat().st_size != entry["size_bytes"]:
            raise ValueError(f"hash/size mismatch: {path}")
    removed = set(published) - set(declared)
    if removed:
        raise ValueError(f"published files dropped from manifest: {sorted(removed)}")
    changed = sorted(p for p in published if declared[p]["sha256"] != published[p]["sha256"])
    if set(changed) - set(UPDATED_CARDS):
        raise ValueError(f"unexpected change to published files: {sorted(set(changed) - set(UPDATED_CARDS))}")
    for path in set(declared) - uploaded:
        if path not in published or declared[path] != published[path]:
            raise ValueError(f"non-uploaded manifest entry differs from published: {path}")
    sums = {}
    for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        checksum, relative = line.split("  ", 1)
        sums[relative] = checksum
    expected = {path: entry["sha256"] for path, entry in declared.items()}
    expected["manifest.json"] = sha256_file(output / "manifest.json")
    if sums != expected:
        raise ValueError("SHA256SUMS differs from manifest")
    return {"status": "PASS", "upload_files": len(present), "changed_published": changed,
            "manifest_entries": len(declared), "tensors_preserved": all(
                declared[p] == published[p] for p in published if p.endswith(".safetensors"))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-manifest", type=Path, required=True)
    parser.add_argument("--live-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-output", type=Path, required=True)
    arguments = parser.parse_args()
    plan = build_upload(WORKTREE_ROOT, BASE_EVAL_RUN, arguments.live_manifest, arguments.live_revision,
                        arguments.output)
    plan["verification"] = verify_upload(arguments.output, arguments.live_manifest)
    arguments.plan_output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(plan["verification"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
