from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RELEASE_ROOT = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = RELEASE_ROOT.parent
RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
sys.path.insert(0, str(RELEASE_ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


verify_release = load_module("verify_release_for_tests", RELEASE_ROOT / "verify_release.py")
build_release = load_module("build_release_for_tests", RELEASE_ROOT / "build_release.py")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_manifest_bundle(root: Path) -> None:
    """Create a two-file generic manifest fixture with independently computed hashes."""
    (root / "adapter").mkdir(parents=True)
    (root / "adapter/model.bin").write_bytes(b"model")
    (root / "result.json").write_text('{"ok": true}\n', encoding="utf-8")
    files = []
    for relative in ("adapter/model.bin", "result.json"):
        path = root / relative
        files.append({"path": relative, "sha256": digest(path), "size_bytes": path.stat().st_size})
    manifest = {"schema_version": 1, "files": files}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [f"{entry['sha256']}  {entry['path']}" for entry in files]
    lines.append(f"{digest(root / 'manifest.json')}  manifest.json")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        make_manifest_bundle(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_valid_manifest_and_checksums_pass(self):
        # Catches incomplete hashing or checksum files that omit the manifest itself.
        result = verify_release.verify_manifest(self.root)
        self.assertEqual(result["files_verified"], 3)
        self.assertEqual(result["payload_files"], 2)

    def test_changed_payload_fails_hash_verification(self):
        # Catches a verifier that trusts manifest declarations without reading file bytes.
        (self.root / "result.json").write_text('{"ok": false}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            verify_release.verify_manifest(self.root)

    def test_unlisted_raw_predictions_are_rejected(self):
        # Catches accidental inclusion of the large raw prediction files in a release.
        (self.root / "raw_predictions.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "raw predictions|unmanifested"):
            verify_release.verify_manifest(self.root)

    def test_parent_traversal_manifest_path_is_rejected(self):
        # Catches a manifest causing verification to read outside the bundle.
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["path"] = "../outside"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            verify_release.verify_manifest(self.root)

    def test_checksum_file_cannot_be_stale(self):
        # Catches updating manifest hashes without regenerating the human-checkable sums.
        (self.root / "SHA256SUMS").write_text("0" * 64 + "  manifest.json\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
            verify_release.verify_manifest(self.root)

    def test_renamed_raw_output_json_is_rejected(self):
        # Catches renaming raw_predictions.json to evade filename-only release checks.
        renamed = self.root / "predictions.json"
        renamed.write_text(json.dumps({"records": [{"raw_output": "ACTION: UPDATE"}]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "raw predictions"):
            verify_release.assert_no_raw_outputs(renamed)

    def test_renamed_nested_resolution_raw_output_is_rejected(self):
        # Catches native-resolution raw text nested below initial/followups in renamed JSON.
        renamed = self.root / "metrics.json"
        renamed.write_text(json.dumps({"records": [{"initial": {"raw_output": "ACTION: UPDATE"}, "followups": {"gold_evidence": {"raw_output": "ACTION: RETAIN"}}}]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "raw predictions"):
            verify_release.assert_no_raw_outputs(renamed)

    def test_release_allowlist_rejects_unapproved_files(self):
        # Catches recursive-copy inclusion of new, unreviewed results or source files.
        self.assertTrue(build_release.is_curated_release_path("results/merged/MERGE-RESULTS.md"))
        self.assertFalse(build_release.is_curated_release_path("results/merged/unapproved.json"))
        self.assertFalse(build_release.is_curated_release_path("source/merge_eval/unapproved.py"))


class ActualReleaseTests(unittest.TestCase):
    def test_builder_cli_works_in_isolated_mode(self):
        # Catches sibling imports that disappear when Python -I omits the script directory.
        result = subprocess.run(
            [sys.executable, "-I", str(RELEASE_ROOT / "build_release.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--raw-root", result.stdout)

    def test_actual_adapter_build_verification_and_rebuild_guard(self):
        # Catches incomplete adapter copies, wrong release anchors, and destructive rebuilds.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "evidencetune-merge-alpha-0.75"
            build_release.build_release(WORKTREE_ROOT, RAW_ROOT, destination)
            result = verify_release.verify_release(destination)
            self.assertEqual(result["adapter_sha256"], verify_release.EXPECTED_ADAPTER_SHA256)
            self.assertGreaterEqual(result["payload_files"], 15)
            self.assertIn("license: cc-by-nc-4.0", (destination / "adapter/README.md").read_text())
            self.assertNotIn("adapter/adapter_model.safetensors", (destination / "adapter/README.md").read_text())
            self.assertIn("adapter_model.safetensors", (destination / "adapter/README.md").read_text())
            card = (destination / "adapter/README.md").read_text()
            self.assertIn("](../REPRODUCE.md)", card)
            self.assertIn("](../SHA256SUMS)", card)
            self.assertIn("](../manifest.json)", card)
            self.assertIn("](merge_provenance.json)", card)
            self.assertIn("](../results/)", card)
            self.assertIn("https://github.com/kendramoss/exsi-lexsi-hackathon", card)
            self.assertIn("../LICENSE-MODEL", card)
            self.assertNotIn("[More Information Needed]", card)
            self.assertTrue((destination / "NOTICE.md").is_file())
            self.assertTrue((destination / "LICENSE").is_file())
            with self.assertRaises(FileExistsError):
                build_release.build_release(WORKTREE_ROOT, RAW_ROOT, destination)


if __name__ == "__main__":
    unittest.main(verbosity=2)
