from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("additive", WORKTREE_ROOT / "public_staging/build_additive_upload.py")
additive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(additive)


def fake_live(root: Path) -> Path:
    tensor = {"path": "adapter_model.safetensors", "sha256": "a" * 64, "size_bytes": 5}
    readme = {"path": "README.md", "sha256": "b" * 64, "size_bytes": 1}
    repro = {"path": "code/release/REPRODUCE.md", "sha256": "c" * 64, "size_bytes": 1}
    old = {"path": "evidence/old.json", "sha256": "d" * 64, "size_bytes": 2}
    path = root / "live_manifest.json"
    path.write_text(json.dumps({"collection": "model_collection", "schema_version": 1,
                                "files": [tensor, readme, repro, old]}), encoding="utf-8")
    return path


class AdditiveUploadTests(unittest.TestCase):
    def test_allowlist_never_overwrites_published_files_except_cards(self):
        items = additive.allowlist(WORKTREE_ROOT, additive.BASE_EVAL_RUN)
        self.assertEqual(len(items), len(set(items)))
        for destination in items:
            self.assertFalse(destination.endswith(".safetensors"))
            self.assertNotIn("..", destination.split("/"))
        self.assertTrue(set(additive.UPDATED_CARDS) <= set(items))

    def test_manifest_preserves_old_entries_and_verifies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = fake_live(root)
            output = root / "upload"
            plan = additive.build_upload(WORKTREE_ROOT, additive.BASE_EVAL_RUN, live, "rev", output)
            result = additive.verify_upload(output, live)
            self.assertTrue(result["tensors_preserved"])
            self.assertEqual(result["changed_published"], ["README.md", "code/release/REPRODUCE.md"])
            self.assertIn("evidence/old.json", {e["path"] for e in
                          json.loads((output / "manifest.json").read_text())["files"]})
            self.assertFalse((output / "adapter_model.safetensors").exists())
            self.assertEqual(len(plan["new_files"]), len(plan["upload_files"]) - 4)

    def test_tampered_upload_file_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = fake_live(root)
            output = root / "upload"
            additive.build_upload(WORKTREE_ROOT, additive.BASE_EVAL_RUN, live, "rev", output)
            (output / "evidence/uncertainty/UNCERTAINTY.md").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                additive.verify_upload(output, live)

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileExistsError):
                additive.build_upload(WORKTREE_ROOT, additive.BASE_EVAL_RUN, fake_live(root), "rev", root)


if __name__ == "__main__":
    unittest.main()
