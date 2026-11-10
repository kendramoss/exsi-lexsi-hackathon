#!/usr/bin/env python3
"""CPU-only, element-wise interpolation of compatible PEFT LoRA safetensors."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import safetensors
from safetensors.numpy import load_file, save_file

MODEL_NAME = "adapter_model.safetensors"
CONFIG_NAME = "adapter_config.json"
README_NAME = "README.md"
PROVENANCE_NAME = "merge_provenance.json"
DEFAULT_ALPHAS = (0.25, 0.50, 0.75)
WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_V7 = WORKSPACE / "results/v7/evtune-next-output/v6_semantic/adapter"
DEFAULT_V8 = WORKSPACE / "results/v8/evtune-v8-output/v8_targeted_two_turn/adapter"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "adapters"
DTYPE_BYTES = {
    "BOOL": 1,
    "U8": 1,
    "I8": 1,
    "F8_E4M3": 1,
    "F8_E5M2": 1,
    "F8_E8M0": 1,
    "I16": 2,
    "U16": 2,
    "F16": 2,
    "BF16": 2,
    "I32": 4,
    "U32": 4,
    "F32": 4,
    "I64": 8,
    "U64": 8,
    "F64": 8,
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_header(path: Path) -> tuple[dict[str, Any], int, int]:
    size = path.stat().st_size
    with path.open("rb") as handle:
        prefix = handle.read(8)
        if len(prefix) != 8:
            raise ValueError(f"incomplete safetensors header length: {path}")
        header_length = struct.unpack("<Q", prefix)[0]
        if header_length > size - 8:
            raise ValueError(f"incomplete safetensors header bytes: {path}")
        header_bytes = handle.read(header_length)
        if len(header_bytes) != header_length:
            raise ValueError(f"incomplete safetensors header bytes: {path}")
    try:
        header = json.loads(header_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid safetensors JSON header: {path}") from error
    if not isinstance(header, dict):
        raise ValueError(f"invalid safetensors header object: {path}")
    return header, header_length, size


def validate_safetensors_file(path: str | Path) -> dict[str, Any]:
    """Validate declared tensor bytes and exact header+data file coverage."""
    path = Path(path)
    header, header_length, size = _read_header(path)
    tensors = header.get("tensors") if "tensors" in header else {
        key: value for key, value in header.items() if key != "__metadata__"
    }
    if not isinstance(tensors, dict) or not tensors:
        raise ValueError(f"safetensors contains no tensor declarations: {path}")

    specifications = {}
    positioned = []
    for name, declaration in tensors.items():
        if not isinstance(name, str) or not isinstance(declaration, dict):
            raise ValueError(f"invalid tensor declaration in {path}")
        dtype = declaration.get("dtype")
        shape = declaration.get("shape")
        offsets = declaration.get("data_offsets")
        if dtype not in DTYPE_BYTES:
            raise ValueError(f"unsupported tensor dtype {dtype!r} for {name}")
        if (
            not isinstance(shape, list)
            or any(isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 0
                   for dimension in shape)
        ):
            raise ValueError(f"invalid shape for tensor {name}")
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or any(isinstance(offset, bool) or not isinstance(offset, int) or offset < 0
                   for offset in offsets)
            or offsets[1] < offsets[0]
        ):
            raise ValueError(f"invalid data offsets for tensor {name}")
        expected_bytes = math.prod(shape) * DTYPE_BYTES[dtype]
        if offsets[1] - offsets[0] != expected_bytes:
            raise ValueError(f"declared byte count does not match shape/dtype for {name}")
        specifications[name] = {"dtype": dtype, "shape": shape}
        positioned.append((offsets[0], offsets[1], name))

    cursor = 0
    for start, end, name in sorted(positioned):
        if start != cursor:
            raise ValueError(f"incomplete/overlapping tensor data offsets at {name}")
        cursor = end
    data_bytes = size - 8 - header_length
    if cursor != data_bytes:
        raise ValueError(
            f"incomplete tensor coverage or wrong file size: declared {cursor} data bytes, "
            f"actual {data_bytes}"
        )
    metadata = header.get("__metadata__", {})
    if not isinstance(metadata, dict):
        raise ValueError(f"invalid safetensors metadata: {path}")
    return {
        "complete": True,
        "size_bytes": size,
        "header_bytes": header_length,
        "tensor_data_bytes": data_bytes,
        "tensor_count": len(specifications),
        "tensors": specifications,
        "metadata": metadata,
    }


def _normalized_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    targets = normalized.get("target_modules")
    if isinstance(targets, list):
        normalized["target_modules"] = sorted(targets)
    return normalized


def _validate_lora_config(config: dict[str, Any], source: Path) -> None:
    if config.get("peft_type") != "LORA":
        raise ValueError(f"adapter_config is not plain LoRA: {source}")
    if config.get("bias", "none") != "none" or config.get("modules_to_save") not in (None, [], {}):
        raise ValueError(f"adapter_config contains non-LoRA trained weights: {source}")
    for field in ("use_dora", "use_qalora", "use_rslora", "use_bdlora"):
        if config.get(field) is True:
            raise ValueError(f"adapter_config uses unsupported LoRA variant {field}: {source}")
    if config.get("lora_ga_config") is not None:
        raise ValueError(f"adapter_config uses unsupported LoRA-GA scaling: {source}")


def _source_description(source: Path) -> dict[str, Any]:
    files = {}
    for file in sorted(source.rglob("*")):
        if file.is_file():
            relative = file.relative_to(source).as_posix()
            files[relative] = {"sha256": sha256_file(file), "size_bytes": file.stat().st_size}
    for required in (MODEL_NAME, CONFIG_NAME):
        if required not in files:
            raise ValueError(f"source adapter is missing {required}: {source}")
    return {"path": str(source.resolve()), "files": files}


def _validate_sources(v7_dir: Path, v8_dir: Path) -> dict[str, Any]:
    v7_file = validate_safetensors_file(v7_dir / MODEL_NAME)
    v8_file = validate_safetensors_file(v8_dir / MODEL_NAME)
    if v7_file["tensors"] != v8_file["tensors"]:
        v7_keys = set(v7_file["tensors"])
        v8_keys = set(v8_file["tensors"])
        if v7_keys != v8_keys:
            raise ValueError("source tensor keys differ")
        for key in sorted(v7_keys):
            left = v7_file["tensors"][key]
            right = v8_file["tensors"][key]
            if left["shape"] != right["shape"]:
                raise ValueError(f"source tensor shape differs for {key}")
            if left["dtype"] != right["dtype"]:
                raise ValueError(f"source tensor dtype differs for {key}")
        raise ValueError("source tensor specifications differ")

    try:
        v7_config = json.loads((v7_dir / CONFIG_NAME).read_text(encoding="utf-8"))
        v8_config = json.loads((v8_dir / CONFIG_NAME).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("invalid adapter_config JSON") from error
    _validate_lora_config(v7_config, v7_dir)
    _validate_lora_config(v8_config, v8_dir)
    if _normalized_config(v7_config) != _normalized_config(v8_config):
        raise ValueError("adapter_config semantics differ beyond target_modules ordering")
    return {
        "identical_keys_shapes_dtypes": True,
        "compatible_adapter_config": True,
        "target_modules_order_ignored": True,
        "tensor_count": v7_file["tensor_count"],
        "tensor_data_bytes": v7_file["tensor_data_bytes"],
        "source_files_complete": True,
    }


def _alpha_value(alpha: float) -> float:
    try:
        value = float(alpha)
    except (TypeError, ValueError) as error:
        raise ValueError("alpha must be a finite number in [0, 1]") from error
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("alpha must be a finite number in [0, 1]")
    return value


def merge_adapters(
    v7_dir: str | Path,
    v8_dir: str | Path,
    output_dir: str | Path,
    alpha: float,
) -> dict[str, Any]:
    """Write alpha*v7 + (1-alpha)*v8, preserving v7 config and recording provenance."""
    alpha = _alpha_value(alpha)
    v7_dir = Path(v7_dir)
    v8_dir = Path(v8_dir)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing merge output: {output_dir}")

    structure = _validate_sources(v7_dir, v8_dir)
    sources = {"v7": _source_description(v7_dir), "v8": _source_description(v8_dir)}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent))
    try:
        v7_tensors = load_file(str(v7_dir / MODEL_NAME))
        v8_tensors = load_file(str(v8_dir / MODEL_NAME))
        merged = {}
        for key in sorted(v7_tensors):
            left = v7_tensors[key]
            right = v8_tensors[key]
            if not np.issubdtype(left.dtype, np.floating):
                raise ValueError(f"cannot interpolate non-floating tensor {key}: {left.dtype}")
            # Float64 arithmetic avoids two float32 roundings; output dtype remains unchanged.
            value = (alpha * left.astype(np.float64) + (1.0 - alpha) * right.astype(np.float64))
            value = np.ascontiguousarray(value.astype(left.dtype))
            if not bool(np.isfinite(value).all()):
                raise ValueError(f"non-finite merged values in {key}")
            merged[key] = value

        model_path = temporary / MODEL_NAME
        source_metadata = validate_safetensors_file(v7_dir / MODEL_NAME)["metadata"]
        save_file(merged, str(model_path), metadata=source_metadata)
        byte_validation = validate_safetensors_file(model_path)
        reloaded = load_file(str(model_path))
        if set(reloaded) != set(merged):
            raise ValueError("reloaded output tensor keys differ from merged tensors")
        for key, expected in merged.items():
            actual = reloaded[key]
            if actual.dtype != expected.dtype or actual.shape != expected.shape:
                raise ValueError(f"reloaded output dtype/shape differs for {key}")
            if not np.array_equal(actual, expected):
                raise ValueError(f"reloaded output values differ for {key}")

        shutil.copyfile(v7_dir / CONFIG_NAME, temporary / CONFIG_NAME)
        if (v7_dir / README_NAME).is_file():
            shutil.copyfile(v7_dir / README_NAME, temporary / README_NAME)
        provenance = {
            "schema_version": 1,
            "operation": "elementwise_lora_weight_interpolation",
            "formula": "merged = alpha * v7 + (1 - alpha) * v8",
            "alpha": alpha,
            "weights": {"v7": alpha, "v8": 1.0 - alpha},
            "arithmetic": "float64 interpolation, cast once to each source tensor dtype",
            "adapter_config_preserved_from": "v7",
            "readme_preserved_from": "v7",
            "sources": sources,
            "structure": structure,
            "output": {
                "adapter_model.safetensors": {
                    "sha256": sha256_file(model_path),
                    "size_bytes": model_path.stat().st_size,
                }
            },
            "validation": {
                **structure,
                "complete_output_bytes": byte_validation["complete"],
                "full_tensor_values_verified": True,
                "all_merged_values_finite": True,
            },
            "tool": {
                "implementation": "merge_eval/merge_lora.py",
                "safetensors_version": safetensors.__version__,
                "numpy_version": np.__version__,
                "device": "CPU only",
            },
        }
        (temporary / PROVENANCE_NAME).write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return {
        "name": output_dir.name,
        "alpha": alpha,
        "path": str(output_dir.resolve()),
        "sha256": provenance["output"][MODEL_NAME]["sha256"],
        "size_bytes": provenance["output"][MODEL_NAME]["size_bytes"],
        "tensor_count": structure["tensor_count"],
        "tensor_data_bytes": structure["tensor_data_bytes"],
        "validation": provenance["validation"],
    }


def merge_all(
    v7_dir: str | Path,
    v8_dir: str | Path,
    output_root: str | Path,
    alphas: Iterable[float] = DEFAULT_ALPHAS,
) -> dict[str, Any]:
    """Create one immutable adapter per alpha and a hash manifest."""
    v7_dir = Path(v7_dir)
    v8_dir = Path(v8_dir)
    output_root = Path(output_root)
    alpha_values = [_alpha_value(alpha) for alpha in alphas]
    names = [f"alpha_{alpha:.2f}" for alpha in alpha_values]
    if len(set(names)) != len(names):
        raise ValueError("alphas must produce distinct output names at two-decimal precision")
    outputs = [
        merge_adapters(v7_dir, v8_dir, output_root / name, alpha)
        for name, alpha in zip(names, alpha_values)
    ]
    manifest = {
        "schema_version": 1,
        "formula": "merged = alpha * v7 + (1 - alpha) * v8",
        "sources": {"v7": _source_description(v7_dir), "v8": _source_description(v8_dir)},
        "outputs": outputs,
        "all_outputs_validated": True,
        "gpu_used": False,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "merge_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v7", type=Path, default=DEFAULT_V7)
    parser.add_argument("--v8", type=Path, default=DEFAULT_V8)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--alphas", type=float, nargs="+", default=DEFAULT_ALPHAS)
    arguments = parser.parse_args()
    manifest = merge_all(arguments.v7, arguments.v8, arguments.output_root, arguments.alphas)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
