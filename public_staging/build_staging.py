#!/usr/bin/env python3
"""Build and verify local-only public model/dataset artifact staging."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
DEFAULT_OUTPUT = WORKTREE_ROOT / ".public_staging/evidencetune-merged-alpha-0.75"
ADAPTER_SHA256 = "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335"
V7_SHA256 = "736dcea313d0a4c54021b2b5a0af6d1dd5d1a0bf6d2c750a2a788e0a5d7dc1fd"
V8_SHA256 = "9985ca4829348a0eb7a32dfae37302921fe4af0485bc1fa114dd869dcc66e837"
sys.path.insert(0, str(WORKTREE_ROOT / "release"))
from model_card import render_model_card  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def verify_selected_adapter(raw_root: Path) -> None:
    path = Path(raw_root) / "merge_eval/adapters/alpha_0.75/adapter_model.safetensors"
    if not path.is_file() or sha256_file(path) != ADAPTER_SHA256:
        raise ValueError("selected adapter hash differs from merge_alpha_0.75")


def is_cache_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe staging path: {value}")
    return path.as_posix()


def assert_publishable_file(relative: str, path: Path) -> None:
    """Reject unresolved Korean raw rows, credentials, and symlink publication."""
    relative = safe_relative(relative)
    lowered = relative.lower()
    name = path.name.lower()
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"staging requires regular non-symlink files: {relative}")
    if "xstest_ko" in lowered or "/korean/" in lowered:
        raise ValueError(f"Korean XSTest raw material is excluded: {relative}")
    if name in {".env", ".env.local", "credentials.json", "credentials", "secrets.json"} or "credential" in name:
        raise ValueError(f"credential file is excluded: {relative}")
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, dict) and row.get("language") == "ko":
                    raise ValueError(f"Korean raw row is excluded: {relative}:{line_number}")
    if path.suffix == ".json":
        document = json.loads(path.read_text(encoding="utf-8"))
        def reject_korean_review(value: Any) -> None:
            if isinstance(value, dict):
                if isinstance(value.get("prompt_id"), str) and value["prompt_id"].startswith("ko-"):
                    raise ValueError(f"Korean review record is excluded: {relative}")
                for item in value.values():
                    reject_korean_review(item)
            elif isinstance(value, list):
                for item in value:
                    reject_korean_review(item)
        reject_korean_review(document)
    if path.suffix.lower() in {".py", ".md", ".txt", ".json", ".jsonl", ".log", ".csv", ".sh", ".html"} or name in {"license", "notice"}:
        text = path.read_text(encoding="utf-8", errors="strict")
        if re.search(r"hf_[A-Za-z0-9]{30,}", text) or re.search(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", text):
            raise ValueError(f"credential-like content is excluded: {relative}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_dataset_card(path: Path) -> dict[str, Any]:
    """Require truthful Hub metadata and an explicit non-tabular viewer choice."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("dataset card metadata front matter is missing")
    try:
        closing = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as error:
        raise ValueError("dataset card metadata front matter is unterminated") from error
    try:
        metadata = yaml.safe_load("".join(lines[1:closing]))
    except yaml.YAMLError as error:
        raise ValueError(f"dataset card metadata is invalid YAML: {error}") from error
    if not isinstance(metadata, dict) or metadata.get("viewer") is not False:
        raise ValueError("dataset card metadata must set viewer: false")
    if metadata.get("license") != "other" or not isinstance(metadata.get("pretty_name"), str):
        raise ValueError("dataset card metadata must declare mixed-license scope and a pretty_name")
    body = "".join(lines[closing + 1:]).lower()
    if "heterogeneous" not in body or "download" not in body:
        raise ValueError("dataset card must explain disabled heterogeneous previews and downloadable files")
    return metadata


def write_collection_integrity(root: Path, collection: str) -> None:
    """Write manifests that remain valid when one collection is uploaded as a repository root."""
    collection_root = root / collection
    files = []
    for path in sorted(collection_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(collection_root).as_posix()
        if relative in {"manifest.json", "SHA256SUMS"} or is_cache_path(relative):
            continue
        assert_publishable_file(relative, path)
        files.append({"path": relative, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    manifest = {"schema_version": 1, "collection": collection, "files": files}
    write_json(collection_root / "manifest.json", manifest)
    sums = [f"{entry['sha256']}  {entry['path']}" for entry in files]
    sums.append(f"{sha256_file(collection_root / 'manifest.json')}  manifest.json")
    (collection_root / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def verify_collection_integrity(root: Path, collection: str) -> None:
    """Verify the exact payload and checksums visible in an individually uploaded collection."""
    collection_root = root / collection
    if collection == "dataset_collection":
        validate_dataset_card(collection_root / "README.md")
    manifest_path = collection_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("collection") != collection:
        raise ValueError(f"invalid collection manifest: {collection}")
    declared = {safe_relative(entry["path"]): entry for entry in manifest["files"]}
    if "manifest.json" in declared or "SHA256SUMS" in declared or len(declared) != len(manifest["files"]):
        raise ValueError(f"duplicate or reserved collection manifest path: {collection}")
    actual = {
        path.relative_to(collection_root).as_posix(): path
        for path in collection_root.rglob("*")
        if (path.is_file() or path.is_symlink())
        and path.relative_to(collection_root).as_posix() not in {"manifest.json", "SHA256SUMS"}
        and not is_cache_path(path.relative_to(collection_root).as_posix())
    }
    if set(actual) != set(declared):
        raise ValueError(f"collection inventory mismatch: {collection}")
    for relative, entry in declared.items():
        path = actual[relative]
        assert_publishable_file(relative, path)
        if path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"collection hash/size mismatch: {collection}/{relative}")
    sums = {}
    for line in (collection_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        checksum, relative = line.split("  ", 1)
        sums[safe_relative(relative)] = checksum
    expected = {relative: entry["sha256"] for relative, entry in declared.items()}
    expected["manifest.json"] = sha256_file(manifest_path)
    if sums != expected:
        raise ValueError(f"collection SHA256SUMS mismatch: {collection}")


def filtered_language_jsonl(source: Path, destination: Path, derivation_path: Path, source_relative: str) -> None:
    """Keep original en/it JSONL row bytes; derive a new file without Korean rows."""
    kept = []
    counts = {"en": 0, "it": 0, "ko_excluded": 0}
    with source.open("rb") as handle:
        for line in handle:
            row = json.loads(line)
            language = row.get("language")
            if language == "ko":
                counts["ko_excluded"] += 1
                continue
            if language not in {"en", "it"}:
                raise ValueError(f"unexpected language in {source_relative}")
            counts[language] += 1
            kept.append(line if line.endswith(b"\n") else line + b"\n")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"".join(kept))
    write_json(derivation_path, {
        "schema_version": 1,
        "source_project_relative_path": source_relative,
        "source_sha256": sha256_file(source),
        "derived_file": destination.name,
        "derived_sha256": sha256_file(destination),
        "counts": counts,
        "method": "whole original JSONL row bytes retained for en/it; Korean rows omitted; raw source unchanged",
    })


def filtered_review_summary(source: Path, destination: Path, derivation_path: Path) -> None:
    """Remove Korean review records; retain only labeled historical aggregate statistics."""
    original = json.loads(source.read_text(encoding="utf-8"))
    derived = dict(original)
    derived["counts"] = [entry for entry in original["counts"] if entry.get("language") in {"en", "it"}]
    derived["proxy_disagreements"] = [
        entry for entry in original["proxy_disagreements"]
        if not str(entry.get("prompt_id", "")).startswith("ko-")
    ]
    historical = {
        "label": "Historical aggregate only, includes Korean; no Korean raw/review rows are present in this file",
        "proxy_agreement": original["proxy_agreement"],
        "reviewed_full_or_partial_refusals": original["reviewed_full_or_partial_refusals"],
        "reviewed_nonanswers": original["reviewed_nonanswers"],
        "reviewed_unclear": original["reviewed_unclear"],
        "sample_size": original["sample_size"],
    }
    for key in ("proxy_agreement", "reviewed_full_or_partial_refusals", "reviewed_nonanswers", "reviewed_unclear"):
        derived.pop(key, None)
    derived["sample_size"] = sum(entry["count"] for entry in derived["counts"])
    derived["review_scope"] = "English/Italian review records only; Korean review records excluded"
    derived["historical_aggregate_including_korean"] = historical
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json(destination, derived)
    write_json(derivation_path, {
        "schema_version": 1,
        "source_project_relative_path": "issue11_overrefusal/review/review_summary.json",
        "source_sha256": sha256_file(source),
        "derived_sha256": sha256_file(destination),
        "review_scope": derived["review_scope"],
        "korean_review_records_excluded": True,
        "raw_source_unchanged": True,
    })


def build_staging(worktree_root: Path, raw_root: Path, output: Path) -> dict[str, Any]:
    worktree_root = Path(worktree_root)
    raw_root = Path(raw_root)
    output = Path(output)
    verify_selected_adapter(raw_root)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite public staging: {output}")
    operations: dict[str, tuple[str, str]] = {}

    def add(origin: str, relative: str, destination: str) -> None:
        destination = safe_relative(destination)
        if destination in operations:
            raise ValueError(f"duplicate staging destination: {destination}")
        source_root = worktree_root if origin == "worktree" else raw_root
        if origin in {"worktree", "raw"} and not (source_root / relative).is_file():
            raise FileNotFoundError(f"required staging source file missing: {source_root / relative}")
        operations[destination] = (origin, relative)

    def add_tree(origin: str, relative: str, destination: str, *, suffixes: set[str] | None = None) -> None:
        base = (worktree_root if origin == "worktree" else raw_root) / relative
        if not base.is_dir():
            raise FileNotFoundError(f"required staging source directory missing: {base}")
        for source in sorted(base.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            if suffixes is not None and source.suffix not in suffixes:
                continue
            child = source.relative_to(base).as_posix()
            add(origin, f"{relative}/{child}", f"{destination}/{child}")

    # Model collection: selected adapter, same-run baseline, and immutable merge inputs/candidates.
    for name in ("adapter_model.safetensors", "adapter_config.json", "merge_provenance.json"):
        add("raw", f"merge_eval/adapters/alpha_0.75/{name}", f"model_collection/{name}")
    add("worktree", "release/MODEL_CARD.md", "model_collection/README.md")
    add("worktree", "release/REPRODUCE.md", "model_collection/code/release/REPRODUCE.md")
    add("worktree", "LICENSE-MODEL", "model_collection/LICENSE-MODEL")
    for name in ("NOTICE.md", "LICENSE-DECISION.md"):
        add("worktree", name, f"model_collection/{name}")
        add("worktree", name, f"dataset_collection/{name}")
    adapters = {
        "baselines/v7": "results/v7/evtune-next-output/v6_semantic/adapter",
        "baselines/v6": "results/final/adapter_v6",
        "provenance/v8": "results/v8/evtune-v8-output/v8_targeted_two_turn/adapter",
        "provenance/merge_alpha_0.25": "merge_eval/adapters/alpha_0.25",
        "provenance/merge_alpha_0.50": "merge_eval/adapters/alpha_0.50",
    }
    for destination, source in adapters.items():
        for name in ("adapter_model.safetensors", "adapter_config.json"):
            add("raw", f"{source}/{name}", f"model_collection/{destination}/{name}")
        provenance = raw_root / source / "merge_provenance.json"
        if provenance.is_file():
            add("raw", f"{source}/merge_provenance.json", f"model_collection/{destination}/merge_provenance.json")
    for arm_root, destination in (
        ("results/v7/evtune-next-output/v6_semantic", "baselines/v7"),
        ("results/v8/evtune-v8-output/v8_targeted_two_turn", "provenance/v8"),
    ):
        for name in ("training.json", "plan.json", "run_state.json", "arm.complete.json", "artifacts.manifest.json"):
            add("raw", f"{arm_root}/{name}", f"model_collection/{destination}/{name}")

    # Dataset collection: source/label packs and exact curated training inputs.
    for source, destination in (
        ("semantic_contrast/packs_v2", "dataset_collection/semantic_contrast/packs_v2"),
        ("v8_data/packs", "dataset_collection/v8_targeted/packs"),
        ("resolution_expand/pack", "dataset_collection/resolution_expand/pack"),
    ):
        add_tree("raw", source, destination)
    add_tree("raw", "issue10_generate", "dataset_collection/issue10")
    add_tree("raw", "issue8_arabic/pack", "dataset_collection/issue8_arabic/pack")
    add_tree("raw", "issue8_arabic_review", "dataset_collection/issue8_arabic/review")
    add_tree("raw", "data_v6", "dataset_collection/historical_v6")
    add_tree("raw", "results/v7/evtune-next-inputs", "dataset_collection/training/v7")
    add_tree("raw", "results/v8/evtune-v8-inputs", "dataset_collection/training/v8")
    add("worktree", "public_staging/DATASET-CARD.md", "dataset_collection/README.md")

    # Saved raw model evidence, same-run summaries, plans, and native-resolution records.
    add_tree("raw", "merge_eval/local_results", "model_collection/evidence/merged/local_results")
    add_tree("raw", "results/v7/evtune-next-output/evaluation", "model_collection/evidence/source_models/v7/evaluation")
    add_tree("raw", "results/v8/evtune-v8-output/evaluation", "model_collection/evidence/source_models/v8/evaluation")
    add_tree("raw", "results/summaries/dpo", "model_collection/evidence/dpo")
    add_tree("raw", "issue10_eval", "model_collection/evidence/issue10")
    add_tree("raw", "issue8_arabic_eval", "model_collection/evidence/issue8_arabic")
    for name in ("merge_run.log", "local_eval.log", "frozen_confirmation.log", "frozen_confirmation_failed_split.log", "EVALUATION_PLAN.md"):
        add("raw", f"merge_eval/{name}", f"model_collection/logs/{name}")
    add("raw", "results/v7/evidencetune-v7-semantic-contrast-private.log", "model_collection/logs/v7-training.log")
    add("raw", "results/v8/evidencetune-v8-targeted-two-turn-private.log", "model_collection/logs/v8-training.log")
    for name in ("RESULTS.md", "results/proxy_summary.json", "results/proxy_rates.csv", "results/run_plan.json", "results/generation.log", "data/provenance.json"):
        add("raw", f"issue11_overrefusal/{name}", f"model_collection/evidence/overrefusal/{name}")

    # Original project code and custom scorers; no Lexsi source tree is vendored.
    for tree in ("analysis", "annotation", "data", "jobs", "local_mps", "natural_annotation", "release/source"):
        add_tree("worktree", tree, f"code/{tree}", suffixes={".py", ".json", ".md", ".sh", ".html"})
    for name in ("demo/build_merged_demo.py", "release/replay_evidence.py", "release/model_card.py", "release/evidence-lock.json", "public_staging/build_staging.py"):
        add("worktree", name, f"code/{name}")
    for tree in ("contract_unification", "next_run", "v8_resolution", "backend_release", "issue7", "issue10_generate", "issue10_eval", "issue8_arabic_eval"):
        add_tree("raw", tree, f"code/{tree}", suffixes={".py"})
    for tree in ("semantic_contrast", "v8_data", "resolution_expand"):
        add_tree("raw", tree, f"code/{tree}", suffixes={".py"})
    add_tree("raw", "issue11_overrefusal/scripts", "code/issue11_overrefusal/scripts", suffixes={".py"})
    for toolkit, version in (("CuratorKIT", "v1.1"), ("SafeTune", "v1.2"), ("AuditKIT", "v1.2")):
        operations[f"third_party/Lexsi/{toolkit}-LSAL-{version}.md"] = ("lexsi", f"{toolkit}/LICENSE.md")

    # Submission and license documentation.
    for name in ("WRITEUP.md", "RESUME.md", "SUBMISSION-DRAFT.md", "ABSTRACT.md", "HF-ARTICLE.md", "PUBLICATION-CHECKLIST.md", "MERGED-DEMO.md", "LICENSE", "LICENSE-MODEL", "LICENSE-DECISION.md", "NOTICE.md"):
        add("worktree", name, name if name.startswith("LICENSE") or name == "NOTICE.md" else f"docs/{name}")
    add("worktree", "public_staging/README.md", "README.md")
    add("worktree", "release/REPRODUCE.md", "docs/REPRODUCE.md")
    add("worktree", "PUBLICATION-RESULTS.json", "docs/PUBLICATION-RESULTS.json")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    source_map = []
    try:
        for destination, (origin, relative) in sorted(operations.items()):
            if origin == "worktree":
                source = worktree_root / relative
            elif origin == "raw":
                source = raw_root / relative
            else:
                source = Path("/Users/anasqumhiyeh/lexsi-koth/repos") / relative
            assert_publishable_file(relative, source)
            target = temporary / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            source_map.append({"staged_path": destination, "origin": origin, "source_project_relative_path": relative})

        (temporary / "model_collection/README.md").write_text(
            render_model_card(worktree_root, "model_collection"), encoding="utf-8"
        )
        filtered_review_summary(
            raw_root / "issue11_overrefusal/review/review_summary.json",
            temporary / "model_collection/evidence/overrefusal/review_summary.en_it.json",
            temporary / "model_collection/evidence/overrefusal/review_summary.en_it.derivation.json",
        )
        filtered_language_jsonl(
            raw_root / "issue11_overrefusal/results/raw_prompts_responses.jsonl",
            temporary / "model_collection/evidence/overrefusal/raw_prompts_responses.en_it.jsonl",
            temporary / "model_collection/evidence/overrefusal/raw_prompts_responses.en_it.derivation.json",
            "issue11_overrefusal/results/raw_prompts_responses.jsonl",
        )
        filtered_language_jsonl(
            raw_root / "issue11_overrefusal/data/prompts.jsonl",
            temporary / "dataset_collection/overrefusal/prompts.en_it.jsonl",
            temporary / "dataset_collection/overrefusal/prompts.en_it.derivation.json",
            "issue11_overrefusal/data/prompts.jsonl",
        )
        for collection in ("model_collection", "dataset_collection"):
            write_collection_integrity(temporary, collection)
        write_json(temporary / "SOURCE-MAP.json", source_map)
        files = []
        for path in sorted(temporary.rglob("*")):
            if path.is_file():
                relative = path.relative_to(temporary).as_posix()
                if is_cache_path(relative):
                    continue
                assert_publishable_file(relative, path)
                files.append({
                    "path": relative,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "collection": relative.split("/", 1)[0] if relative.startswith(("model_collection/", "dataset_collection/")) else "shared",
                })
        manifest = {
            "schema_version": 1,
            "staging_id": "evidencetune-merged-alpha-0.75-local-public-staging-2026-11-10",
            "publication_performed": False,
            "collections": ["dataset_collection", "model_collection"],
            "code_license": "MIT",
            "adapter_license": "CC-BY-NC-4.0",
            "selected_adapter": {
                "path": "model_collection/adapter_model.safetensors",
                "sha256": ADAPTER_SHA256,
                "formula": "0.75 * v7 + 0.25 * v8",
            },
            "korean_xstest_raw_rows": "excluded_unresolved_license",
            "excluded": ["credentials and environment files", "Korean XSTest raw rows", "rejected natural SciFact packs", "vendor caches", "third-party Lexsi source trees"],
            "source_adapters": {
                "v7": {"path": "model_collection/baselines/v7/adapter_model.safetensors", "sha256": V7_SHA256},
                "v8": {"path": "model_collection/provenance/v8/adapter_model.safetensors", "sha256": V8_SHA256},
            },
            "files": files,
        }
        write_json(temporary / "manifest.json", manifest)
        sums = [f"{entry['sha256']}  {entry['path']}" for entry in files]
        sums.append(f"{sha256_file(temporary / 'manifest.json')}  manifest.json")
        (temporary / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        verify_staging(temporary)
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def verify_staging(root: Path) -> dict[str, Any]:
    root = Path(root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("publication_performed") is not False or manifest.get("korean_xstest_raw_rows") != "excluded_unresolved_license":
        raise ValueError("staging publication/exclusion declaration is invalid")
    validate_dataset_card(root / "dataset_collection/README.md")
    declared = {safe_relative(entry["path"]): entry for entry in manifest["files"]}
    actual = {
        path.relative_to(root).as_posix(): path for path in root.rglob("*")
        if (path.is_file() or path.is_symlink()) and not is_cache_path(path.relative_to(root).as_posix())
    }
    allowed = set(declared) | {"manifest.json", "SHA256SUMS"}
    if set(actual) != allowed:
        raise ValueError(f"staging inventory mismatch: extras={sorted(set(actual)-allowed)}, missing={sorted(allowed-set(actual))}")
    for relative, entry in declared.items():
        path = actual[relative]
        assert_publishable_file(relative, path)
        if path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"staging hash/size mismatch: {relative}")
    for name, reference in manifest["source_adapters"].items():
        path = root / reference["path"]
        if sha256_file(path) != reference["sha256"]:
            raise ValueError(f"immutable source adapter mismatch: {name}")
    selected = manifest["selected_adapter"]
    if selected["formula"] != "0.75 * v7 + 0.25 * v8" or selected["sha256"] != ADAPTER_SHA256 or sha256_file(root / selected["path"]) != ADAPTER_SHA256:
        raise ValueError("selected adapter manifest/hash mismatch")
    sums = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        checksum, relative = line.split("  ", 1)
        sums[safe_relative(relative)] = checksum
    expected = {relative: entry["sha256"] for relative, entry in declared.items()}
    expected["manifest.json"] = sha256_file(manifest_path)
    if sums != expected:
        raise ValueError("staging SHA256SUMS mismatch")
    for collection in ("model_collection", "dataset_collection"):
        verify_collection_integrity(root, collection)
    return {
        "status": "PASS",
        "files_verified": len(declared) + 1,
        "model_files": sum(entry["collection"] == "model_collection" for entry in declared.values()),
        "dataset_files": sum(entry["collection"] == "dataset_collection" for entry in declared.values()),
        "source_adapters_verified": len(manifest["source_adapters"]),
        "korean_raw_rows": 0,
        "publication_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree-root", type=Path, default=WORKTREE_ROOT)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    if arguments.verify:
        result = verify_staging(arguments.output)
    else:
        manifest = build_staging(arguments.worktree_root, arguments.raw_root, arguments.output)
        result = {"status": "PASS", "output": str(arguments.output), "payload_files": len(manifest["files"])}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
