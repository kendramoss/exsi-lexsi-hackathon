#!/usr/bin/env python3
"""Verify an EvidenceTune merged-model release without network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_ADAPTER_SHA256 = "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335"
EXPECTED_ADAPTER_SIZE = 120_981_200
EXPECTED_SELECTION_SHA256 = "e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b"
EXPECTED_FROZEN_SUMMARY_SHA256 = "3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d"
RAW_PREDICTION_NAMES = {"raw_predictions.json", "resolution_raw.json", "raw_prompts_responses.jsonl"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"unsafe manifest path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe manifest path: {value!r}")
    return path.as_posix()


def parse_sha256sums(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            checksum, relative = line.split("  ", 1)
        except ValueError as error:
            raise ValueError("invalid SHA256SUMS line") from error
        relative = safe_relative_path(relative)
        if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
            raise ValueError("invalid SHA256SUMS checksum")
        if relative in result:
            raise ValueError(f"duplicate SHA256SUMS path: {relative}")
        result[relative] = checksum
    return result


def assert_no_raw_outputs(path: Path) -> None:
    """Reject raw model records even when renamed to a curated-looking JSON filename."""
    if path.suffix not in {".json", ".jsonl"}:
        return
    documents = []
    if path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                documents.append(json.loads(line))
    else:
        documents.append(load_json(path))
    def contains_raw_record(value: Any) -> bool:
        if isinstance(value, dict):
            if "raw_output" in value or ("prompt" in value and "response" in value and "model" in value):
                return True
            return any(contains_raw_record(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_raw_record(item) for item in value)
        return False

    for document in documents:
        if isinstance(document, dict) and "raw_predictions" in document:
            raise ValueError(f"raw predictions are not allowed in the release: {path.name}")
        if contains_raw_record(document):
            raise ValueError(f"raw predictions are not allowed in the release: {path.name}")


def verify_manifest(bundle: Path) -> dict[str, Any]:
    """Verify every payload byte, SHA256SUMS, and the exact bundle file inventory."""
    bundle = Path(bundle)
    manifest_path = bundle / "manifest.json"
    sums_path = bundle / "SHA256SUMS"
    if not bundle.is_dir() or not manifest_path.is_file() or not sums_path.is_file():
        raise ValueError("release must contain manifest.json and SHA256SUMS")
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("unsupported or incomplete release manifest")

    declared: dict[str, dict[str, Any]] = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise ValueError("invalid manifest file entry")
        relative = safe_relative_path(entry.get("path"))
        if relative in {"manifest.json", "SHA256SUMS"} or relative in declared:
            raise ValueError(f"duplicate or reserved manifest path: {relative}")
        if Path(relative).name in RAW_PREDICTION_NAMES or "/batches/" in f"/{relative}":
            raise ValueError(f"raw predictions are not allowed in the release: {relative}")
        declared[relative] = entry

    actual = {
        path.relative_to(bundle).as_posix(): path
        for path in bundle.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    allowed = set(declared) | {"manifest.json", "SHA256SUMS"}
    extras = sorted(set(actual) - allowed)
    missing = sorted(allowed - set(actual))
    if extras or missing:
        raise ValueError(f"unmanifested or missing release files; extras={extras}, missing={missing}")

    for relative, entry in declared.items():
        path = actual[relative]
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"release payload is not a regular file: {relative}")
        assert_no_raw_outputs(path)
        if sha256_file(path) != entry.get("sha256"):
            raise ValueError(f"sha256 mismatch: {relative}")
        if path.stat().st_size != entry.get("size_bytes"):
            raise ValueError(f"size mismatch: {relative}")

    expected_sums = {relative: entry["sha256"] for relative, entry in declared.items()}
    expected_sums["manifest.json"] = sha256_file(manifest_path)
    if parse_sha256sums(sums_path) != expected_sums:
        raise ValueError("SHA256SUMS does not match the manifest and payload")
    return {
        "status": "PASS",
        "payload_files": len(declared),
        "files_verified": len(declared) + 1,
        "manifest_sha256": expected_sums["manifest.json"],
    }


def verify_release(bundle: Path) -> dict[str, Any]:
    """Verify generic integrity plus the locked merged-model evidence anchors."""
    bundle = Path(bundle)
    result = verify_manifest(bundle)
    adapter_path = bundle / "adapter/adapter_model.safetensors"
    adapter_sha256 = sha256_file(adapter_path)
    if adapter_sha256 != EXPECTED_ADAPTER_SHA256 or adapter_path.stat().st_size != EXPECTED_ADAPTER_SIZE:
        raise ValueError("merged adapter hash or size differs from the selected alpha=0.75 artifact")
    card = (bundle / "adapter/README.md").read_text(encoding="utf-8")
    if "license: cc-by-nc-4.0" not in card or "Tiny Aya Global, Cohere Labs" not in card or "[More Information Needed]" in card:
        raise ValueError("adapter root does not contain the completed CC BY-NC model card")

    selection_path = bundle / "results/selection.json"
    frozen_path = bundle / "results/frozen_summary.json"
    validation_path = bundle / "results/frozen_validation.json"
    if sha256_file(selection_path) != EXPECTED_SELECTION_SHA256:
        raise ValueError("dev selection hash differs from the locked selection")
    if sha256_file(frozen_path) != EXPECTED_FROZEN_SUMMARY_SHA256:
        raise ValueError("frozen summary hash differs from the verified confirmation")

    selection = load_json(selection_path)
    frozen = load_json(frozen_path)
    validation = load_json(validation_path)
    provenance = load_json(bundle / "adapter/merge_provenance.json")
    if selection.get("selected_model") != "merge_alpha_0.75" or selection.get("selection_split") != "dev_only":
        raise ValueError("release selection is not the locked dev-only merged model")
    if selection.get("frozen_test_used_for_selection") is not False:
        raise ValueError("frozen cases were used for selection")
    if frozen.get("confirmation_only") is not True or frozen.get("selection_unchanged") is not True:
        raise ValueError("frozen evidence is not confirmation-only")
    if not str(frozen.get("backend", "")).startswith("local Apple MPS bf16"):
        raise ValueError("frozen comparison backend is not Apple MPS bf16")
    if validation.get("raw_predictions_verified") != 1020 or validation.get("status") != "PASS":
        raise ValueError("frozen raw-record verification is incomplete")
    if provenance.get("weights") != {"v7": 0.75, "v8": 0.25}:
        raise ValueError("adapter provenance has the wrong interpolation weights")
    result.update({
        "release_id": load_json(bundle / "manifest.json").get("release_id"),
        "adapter_sha256": adapter_sha256,
        "selection_sha256": EXPECTED_SELECTION_SHA256,
        "frozen_summary_sha256": EXPECTED_FROZEN_SUMMARY_SHA256,
        "frozen_raw_records_verified": 1020,
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(verify_release(arguments.bundle), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
