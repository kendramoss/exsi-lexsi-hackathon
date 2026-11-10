from __future__ import annotations

import importlib
import json
import hashlib
import base64
import subprocess
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path("/Users/anasqumhiyeh/.claude/worktrees/exsi-contradiction")
sys.path.insert(0, str(ROOT))
flow = importlib.import_module("contradiction_spike.kaggle_flow")
packager = importlib.import_module("contradiction_spike.package_notebook")


class KaggleFlowTests(unittest.TestCase):
    def record(self, case_id, condition, truth, success=True):
        return {
            "input": f"{case_id}-{condition}", "raw_output": "unused",
            "metadata": {"case_id": case_id, "condition": condition, "truth": truth,
                         "split": "dev", "family": "numeric_conditions", "lexical_trap": False},
            "evaluation": {"format_ok": success, "action_ok": None if condition == "solo" else success,
                           "answer_ok": success, "task_success": success,
                           "whole_window_answer_ok": success, "terminal": success},
        }

    def test_truth_slices_include_all_five_pair_and_denominators(self):
        records = [self.record("no-case", condition, "no") for condition in
                   ("valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo")]
        summary = flow.summarize_with_truth(records, split="dev", expected_cases=1)
        no = summary["by_truth"]["no"]
        self.assertEqual(no["rows"], 5)
        self.assertEqual(no["cases"], 1)
        self.assertEqual(no["correction_rows"], 4)
        self.assertEqual(no["pairs"], 1)
        self.assertEqual(no["task_success"], 1.0)
        self.assertEqual(no["all_five_task_success"], 1.0)
        self.assertEqual(no["valid_unsupported_toward_pair_success"], 1.0)

    def test_pair_requires_valid_and_unsupported_toward(self):
        records = [self.record("no-case", condition, "no", success=condition != "valid") for condition in
                   ("valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo")]
        summary = flow.summarize_with_truth(records, split="dev", expected_cases=1)
        self.assertEqual(summary["by_truth"]["no"]["valid_unsupported_toward_pair_success"], 0.0)

    def test_evaluation_plan_has_only_two_models_and_no_frozen_inputs(self):
        plan = flow.dev_evaluation_plan(Path("/semantic"), Path("/targeted"), Path("/resolution"))
        self.assertEqual(plan["model_order"], ["merge_alpha_0.75", "contradiction_sft"])
        serialized = json.dumps(plan)
        self.assertNotIn("frozen_test", serialized)
        self.assertNotIn("issue10", serialized)
        self.assertEqual(set(plan["datasets"]), {"semantic_dev", "v8_targeted_dev", "resolution_dev"})

    def test_notebook_is_private_single_candidate_and_has_no_paid_or_frozen_path(self):
        notebook = packager.build_notebook()
        text = json.dumps(notebook)
        self.assertIn("contradiction_spike.kaggle_flow", text)
        self.assertIn("merge_alpha_0.75", text)
        self.assertNotIn("frozen_test", text)
        self.assertNotIn("DPO", "".join(notebook["cells"][2]["source"]))
        self.assertNotIn("hf.co/jobs", text)
        self.assertNotIn("epochs\": 2", text)

    def test_packaged_import_uses_actual_kaggle_mount_location(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".contradiction_spike") as tmp:
            mount = Path(tmp) / "dataset-version-mount"
            package = mount / "contradiction_spike"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (mount / "kaggle" / "input").mkdir(parents=True)
            code_mounts = flow.packaged_code_roots(mount)
            self.assertIn(mount, code_mounts)
            self.assertNotIn(mount / "kaggle" / "input", code_mounts)

    def test_notebook_embeds_exact_bytes_and_imports_before_secret(self):
        notebook = packager.build_notebook()
        sources = flow.dependency_source_inventory()
        embedded = flow.embedded_module_payloads()
        self.assertEqual(len(sources), 43)
        self.assertEqual(sum(path.stat().st_size for path in sources.values()), 7590443)
        for name, record in embedded.items():
            payload = base64.b64decode(record["base64"])
            self.assertEqual(payload, sources[name].read_bytes())
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])
        metadata = notebook["metadata"]
        self.assertNotIn("contradiction_spike_embedded", metadata)
        self.assertEqual(metadata["contradiction_spike_embedded_file_count"], 43)
        self.assertEqual(metadata["contradiction_spike_embedded_raw_bytes"], 7590443)
        self.assertNotIn("base64", json.dumps(metadata))
        compressed = packager.compress_embedded_payload(embedded)
        setup = "".join(notebook["cells"][0]["source"])
        self.assertEqual(setup.count(compressed), 1)
        self.assertIn("lzma.decompress", setup)
        self.assertIn("hashlib.sha256(payload).hexdigest()", setup)
        self.assertIn("/kaggle/working", setup)
        self.assertIn("from backend_release.train_driver import run_plan", setup)
        self.assertNotIn("HF_TOKEN", setup)
        self.assertIn("HF_TOKEN", "".join(notebook["cells"][2]["source"]))
        self.assertNotIn("evtune-contradiction-code", json.dumps(notebook))
        self.assertNotIn("evtune-v8-code", json.dumps(notebook))

    def test_static_dependency_inventory_covers_execution_graph(self):
        expected = {
            "contradiction_spike/__init__.py", "contradiction_spike/spike.py", "contradiction_spike/kaggle_flow.py",
            "backend_release/__init__.py", "backend_release/recovery.py", "backend_release/train_driver.py",
            "contract_unification/contract_v2.py", "next_run/kaggle_next_flow.py",
            "issue7/__init__.py", "issue7/clarification_eval.py",
            "v8_resolution/__init__.py", "v8_resolution/resolution.py", "v8_resolution/pilot.py",
            "v8_resolution/kaggle_integration.py",
        }
        self.assertEqual(set(flow.code_source_inventory()), expected)
        data = flow.data_source_inventory()
        for required in ("payload/data/preregistration.json", "payload/data/train_source.jsonl", "payload/data/train_labels.json",
                         "payload/data/curated/sft_alpaca.jsonl", "payload/data/data_manifest.json",
                         "payload/semantic/dev_source.jsonl", "payload/semantic/dev_labels.json", "payload/semantic/MANIFEST.json",
                         "payload/targeted/dev_source.jsonl", "payload/targeted/dev_labels.json", "payload/targeted/MANIFEST.json",
                         "payload/data/resolution_dev/dev_source.jsonl", "payload/data/resolution_dev/dev_labels.json",
                         "payload/data/resolution_dev/manifest.json"):
            self.assertIn(required, data)
        self.assertEqual(set(flow.dependency_source_inventory()), expected | set(data))

    def test_clean_environment_without_embedded_closure_rejects_backend(self):
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", "import backend_release.train_driver"],
                                   capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("No module named 'backend_release'", completed.stderr)

    def test_clean_environment_without_embedded_data_rejects_preregistration(self):
        command = "from pathlib import Path; Path('/kaggle/input/evtune-contradiction-data/preregistration.json').read_text()"
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", command], capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("FileNotFoundError", completed.stderr)

    def test_materialized_embedded_bytes_import_full_graph_without_code_datasets(self):
        notebook = packager.build_notebook()
        with tempfile.TemporaryDirectory(dir=ROOT / ".contradiction_spike") as tmp:
            packager.materialize_compressed_payload(packager.compress_embedded_payload(flow.embedded_module_payloads()), Path(tmp))
            command = (
                "import sys,json,hashlib; from pathlib import Path; sys.path.insert(0, %r); "
                "import backend_release.train_driver, contract_unification.contract_v2, next_run.kaggle_next_flow; "
                "import issue7.clarification_eval, v8_resolution.kaggle_integration; "
                "from contradiction_spike.kaggle_flow import BASELINE,verify_dev_inputs,training_plan; "
                "root=Path(%r); data=root/'payload/data'; pre=json.loads((data/'preregistration.json').read_text()); "
                "side=json.loads((data/'preregistration.sha256.json').read_text()); "
                "h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); assert h(data/'preregistration.json')==side['sha256']; "
                "manifest=json.loads((data/'data_manifest.json').read_text()); "
                "assert all(h(data/r['path'])==r['sha256'] for r in manifest['files'].values()); "
                "assert sum(1 for _ in (data/'curated/sft_alpaca.jsonl').open())==600; "
                "verify_dev_inputs(pre,root/'payload/semantic',root/'payload/targeted',data/'resolution_dev'); "
                "assert training_plan(data,root/'adapter')['arms'][0]['rows']==600"
            ) % (tmp, tmp)
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            completed = subprocess.run([sys.executable, "-I", "-B", "-c", command], capture_output=True, text=True, env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_kernel_metadata_removes_all_kaggle_dataset_dependencies(self):
        metadata = json.loads((ROOT / ".contradiction_spike" / "kaggle" / "kernel" / "kernel-metadata.json").read_text())
        self.assertEqual(metadata["dataset_sources"], [])

    def test_notebook_uses_public_hash_pinned_adapter_not_kaggle_weights(self):
        notebook = packager.build_notebook()
        text = json.dumps(notebook)
        self.assertIn("Mizore66/evidencetune-merged-alpha-0.75", text)
        self.assertIn("adapter_model.safetensors", text)
        self.assertNotIn("evtune-merged-alpha-075", text)
        self.assertNotIn("/kaggle/input", text)

    def test_notebook_retains_working_v8_dependency_versions(self):
        install = "".join(packager.build_notebook()["cells"][1]["source"])
        for pin in ("transformers==5.22.1", "peft==0.21.2", "datasets==5.1.0",
                    "accelerate==1.15.0", "trl==1.14.2", "a869414b6825e41174e74cd64832d2dcf8f6a9e7",
                    "dd9e835301fcddc74a37501d9e207a5a060d209f", "71316da345784ff220d5ed59337441a59ab31526"):
            self.assertIn(pin, install)
        self.assertIn("pip uninstall -y torchao", install)

    def test_preregistration_verification_rejects_changed_hash(self):
        with self.assertRaises(ValueError):
            flow.verify_preregistration_document({"training_authorized": True}, "expected", "actual")

    def test_dev_inputs_must_match_preregistered_hashes(self):
        import copy
        from contradiction_spike.spike import build_preregistration
        raw = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
        prereg = build_preregistration(raw, ROOT)
        flow.verify_dev_inputs(prereg, raw / "semantic_contrast" / "packs_v2",
                               raw / "v8_data" / "packs", raw / "resolution_expand" / "pack")
        changed = copy.deepcopy(prereg)
        changed["dev"]["semantic_dev"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            flow.verify_dev_inputs(changed, raw / "semantic_contrast" / "packs_v2",
                                   raw / "v8_data" / "packs", raw / "resolution_expand" / "pack")


if __name__ == "__main__":
    unittest.main()
