from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


demo = load_module("merged_demo_for_tests", DEMO_ROOT / "build_merged_demo.py")


class MergedDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = demo.build_demo(RAW_ROOT)

    def test_saved_predictions_produce_first_complete_case_and_headline_scores(self):
        # Catches fabricated examples, incomplete matched cases, and cross-backend headline mixing.
        self.assertEqual(self.payload["illustration"]["case_id"], "sc-01-25")
        self.assertEqual(len(self.payload["illustration"]["records"]), 5)
        self.assertEqual(self.payload["model"]["adapter_sha256"], demo.EXPECTED_ADAPTER_SHA256)
        semantic = self.payload["scoreboards"]["semantic_frozen_test"]
        self.assertEqual(semantic["arms"]["merge_alpha_0.75"]["task_success"], 0.925)
        self.assertEqual(semantic["arms"]["baseline_v7"]["task_success"], 0.8875)
        demo.verify_demo(self.payload, RAW_ROOT)

    def test_raw_output_tampering_is_rejected(self):
        # Catches edited demo text that no longer matches its recorded-output hash.
        payload = copy.deepcopy(self.payload)
        payload["illustration"]["records"][0]["outputs"]["merge_alpha_0.75"]["raw_output"] = "ACTION: RETAIN\nANSWER: no"
        with self.assertRaisesRegex(ValueError, "raw_output sha256"):
            demo.verify_demo(payload)

    def test_backend_mixing_is_rejected(self):
        # Catches placing a historical Kaggle arm in the merged Apple MPS comparison.
        payload = copy.deepcopy(self.payload)
        payload["scoreboards"]["semantic_frozen_test"]["arms"]["baseline_v7"]["backend"] = "Kaggle fp16"
        with self.assertRaisesRegex(ValueError, "backend"):
            demo.verify_demo(payload)

    def test_headline_score_tampering_is_rejected(self):
        # Catches scorecard edits that diverge from the frozen confirmation anchors.
        payload = copy.deepcopy(self.payload)
        payload["scoreboards"]["semantic_frozen_test"]["arms"]["merge_alpha_0.75"]["task_success"] = 0.95
        with self.assertRaisesRegex(ValueError, "scoreboard"):
            demo.verify_demo(payload)

    def test_written_payload_is_machine_verifiable(self):
        # Catches non-deterministic serialization or a file that differs from the returned object.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "demo_merged_data.json"
            demo.write_demo(self.payload, path)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, self.payload)
            demo.verify_demo(path)

    def test_each_frozen_raw_input_hash_is_checked_before_json_loading(self):
        # Catches changed or malformed raw bytes being parsed before their identity is verified.
        for model in demo.MODELS:
            for view in demo.VIEWS:
                with self.subTest(model=model, view=view), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    for relative in (
                        "merge_eval/local_results/evaluation/selection.json",
                        "merge_eval/local_results/frozen_confirmation/frozen_summary.json",
                        "merge_eval/adapters/alpha_0.75/adapter_model.safetensors",
                    ):
                        destination = root / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.symlink_to(RAW_ROOT / relative)
                    for directory in ("semantic_contrast", "v8_data"):
                        (root / directory).symlink_to(RAW_ROOT / directory, target_is_directory=True)
                    changed = demo.raw_relative(model, view)
                    for source_model in demo.MODELS:
                        for source_view in demo.VIEWS:
                            relative = demo.raw_relative(source_model, source_view)
                            destination = root / relative
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            if relative == changed:
                                destination.write_bytes(b"not valid json")
                            else:
                                destination.symlink_to(RAW_ROOT / relative)
                    with self.assertRaisesRegex(ValueError, "raw prediction sha256"):
                        demo.build_demo(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
