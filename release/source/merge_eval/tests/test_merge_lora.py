from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file, save_file

MERGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MERGE_ROOT))

from merge_lora import merge_adapters, merge_all, validate_safetensors_file  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(target_modules=None) -> dict:
    return {
        "peft_type": "LORA",
        "r": 16,
        "lora_alpha": 32,
        "target_modules": target_modules or ["q_proj", "v_proj"],
        "bias": "none",
        "modules_to_save": None,
        "use_dora": False,
        "use_qalora": False,
        "use_rslora": False,
    }


class MergeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temporary.name)
        self.v7 = self.root / "v7"
        self.v8 = self.root / "v8"
        self.output = self.root / "merged"
        for path in (self.v7, self.v8):
            path.mkdir()
            (path / "adapter_config.json").write_text(
                json.dumps(config(), indent=2) + "\n", encoding="utf-8"
            )
            (path / "README.md").write_text("source adapter\n", encoding="utf-8")
        save_file(
            {
                "layer.lora_A.weight": np.array([[0.0, 4.0, -8.0]], dtype=np.float32),
                "layer.lora_B.weight": np.full((2, 2), 2.0, dtype=np.float32),
            },
            str(self.v7 / "adapter_model.safetensors"),
            metadata={"format": "pt"},
        )
        save_file(
            {
                "layer.lora_A.weight": np.array([[4.0, 8.0, 4.0]], dtype=np.float32),
                "layer.lora_B.weight": np.full((2, 2), -2.0, dtype=np.float32),
            },
            str(self.v8 / "adapter_model.safetensors"),
            metadata={"format": "pt"},
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_merge_interpolates_and_preserves_config_and_provenance(self):
        # Catches reversed weights, tensor omission, config drift, and missing source identity.
        (self.v8 / "adapter_config.json").write_text(
            json.dumps(config(["v_proj", "q_proj"]), indent=2) + "\n", encoding="utf-8"
        )
        result = merge_adapters(self.v7, self.v8, self.output, 0.25)
        merged = load_file(str(self.output / "adapter_model.safetensors"))
        np.testing.assert_array_equal(
            merged["layer.lora_A.weight"],
            np.array([[3.0, 7.0, 1.0]], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            merged["layer.lora_B.weight"], np.full((2, 2), -1.0, dtype=np.float32)
        )
        self.assertEqual(merged["layer.lora_A.weight"].dtype, np.float32)
        self.assertEqual(
            (self.output / "adapter_config.json").read_bytes(),
            (self.v7 / "adapter_config.json").read_bytes(),
        )
        self.assertEqual(
            (self.output / "README.md").read_bytes(),
            (self.v7 / "README.md").read_bytes(),
        )
        provenance = json.loads((self.output / "merge_provenance.json").read_text())
        self.assertEqual(provenance["alpha"], 0.25)
        self.assertEqual(provenance["weights"], {"v7": 0.25, "v8": 0.75})
        self.assertEqual(
            provenance["sources"]["v7"]["files"]["adapter_model.safetensors"]["sha256"],
            sha256(self.v7 / "adapter_model.safetensors"),
        )
        self.assertEqual(
            provenance["sources"]["v8"]["files"]["adapter_config.json"]["sha256"],
            sha256(self.v8 / "adapter_config.json"),
        )
        self.assertEqual(provenance["validation"]["complete_output_bytes"], True)
        self.assertEqual(provenance["validation"]["full_tensor_values_verified"], True)
        self.assertEqual(result["tensor_count"], 2)

    def test_merge_rejects_key_shape_and_dtype_mismatches(self):
        # Catches broadcasting or silently dropping tensors when adapter structures differ.
        cases = {
            "keys": {
                "other.lora_A.weight": np.zeros((1, 3), dtype=np.float32),
                "layer.lora_B.weight": np.full((2, 2), -2.0, dtype=np.float32),
            },
            "shape": {
                "layer.lora_A.weight": np.zeros((1, 4), dtype=np.float32),
                "layer.lora_B.weight": np.full((2, 2), -2.0, dtype=np.float32),
            },
            "dtype": {
                "layer.lora_A.weight": np.zeros((1, 3), dtype=np.float16),
                "layer.lora_B.weight": np.full((2, 2), -2.0, dtype=np.float32),
            },
        }
        for label, tensors in cases.items():
            with self.subTest(label=label):
                save_file(tensors, str(self.v8 / "adapter_model.safetensors"))
                with self.assertRaisesRegex(ValueError, label):
                    merge_adapters(self.v7, self.v8, self.root / f"merged-{label}", 0.5)

    def test_merge_rejects_incompatible_config(self):
        # Catches mixing adapters whose LoRA scaling or base target differs despite equal tensors.
        changed = config()
        changed["r"] = 8
        (self.v8 / "adapter_config.json").write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "adapter_config"):
            merge_adapters(self.v7, self.v8, self.output, 0.5)

    def test_merge_rejects_invalid_alpha_without_creating_output(self):
        # Catches extrapolation and NaN weights when only interpolation is allowed.
        for alpha in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(alpha=alpha):
                with self.assertRaisesRegex(ValueError, "alpha"):
                    merge_adapters(self.v7, self.v8, self.output, alpha)
                self.assertFalse(self.output.exists())

    def test_merge_refuses_to_overwrite_existing_output(self):
        # Catches destroying a prior run or mixing bytes from two merge recipes.
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            merge_adapters(self.v7, self.v8, self.output, 0.5)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_merge_all_writes_requested_adapters_and_manifest(self):
        # Catches missing alpha arms and incomplete cross-artifact output hashes.
        destination = self.root / "arms"
        manifest = merge_all(self.v7, self.v8, destination, (0.25, 0.5, 0.75))
        self.assertEqual([entry["alpha"] for entry in manifest["outputs"]], [0.25, 0.5, 0.75])
        for entry in manifest["outputs"]:
            model = destination / entry["name"] / "adapter_model.safetensors"
            self.assertTrue(model.is_file())
            self.assertEqual(entry["sha256"], sha256(model))
            self.assertEqual(entry["size_bytes"], model.stat().st_size)


class SafetensorsCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temporary.name)
        self.path = self.root / "tensor.safetensors"
        save_file(
            {"x": np.arange(6, dtype=np.float32).reshape(2, 3)},
            str(self.path),
            metadata={"format": "pt"},
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_file_reports_declared_tensor_bytes(self):
        # Catches a validator that checks only that the header can be parsed.
        result = validate_safetensors_file(self.path)
        self.assertTrue(result["complete"])
        self.assertEqual(result["tensor_count"], 1)
        self.assertEqual(result["tensor_data_bytes"], 24)
        self.assertEqual(result["size_bytes"], self.path.stat().st_size)

    def test_truncated_and_trailing_bytes_are_rejected(self):
        # Catches accepting incomplete tensor data or unaccounted output bytes.
        original = self.path.read_bytes()
        for label, payload in (("truncated", original[:-1]), ("trailing", original + b"x")):
            with self.subTest(label=label):
                self.path.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "complete|size|offsets"):
                    validate_safetensors_file(self.path)


if __name__ == "__main__":
    unittest.main()
