from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml


WORKTREE_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
STAGING_ROOT = WORKTREE_ROOT / "public_staging"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


staging = load_module("public_staging_for_tests", STAGING_ROOT / "build_staging.py")


class PublicStagingTests(unittest.TestCase):
    def test_korean_rows_and_credential_files_are_rejected(self):
        # Catches unresolved-license rows or credentials entering publishable staging.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            korean = root / "responses.jsonl"
            korean.write_text('{"language":"ko","prompt":"raw"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Korean"):
                staging.assert_publishable_file("responses.jsonl", korean)
            credential = root / "credentials.json"
            credential.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "credential"):
                staging.assert_publishable_file("credentials.json", credential)

    def test_wrong_selected_adapter_is_rejected_before_copying(self):
        # Catches staging an adapter whose bytes differ from the selected merged artifact.
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary)
            adapter = raw / "merge_eval/adapters/alpha_0.75/adapter_model.safetensors"
            adapter.parent.mkdir(parents=True)
            adapter.write_bytes(b"wrong adapter")
            with self.assertRaisesRegex(ValueError, "selected adapter"):
                staging.verify_selected_adapter(raw)

    def test_complete_staging_has_portable_split_collections_and_hashes(self):
        # Catches incomplete evidence, absolute manifest paths, and mixed model/dataset collections.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            cache = destination / "__pycache__/ignored.pyc"
            cache.parent.mkdir()
            cache.write_bytes(b"cache")
            result = staging.verify_staging(destination)
            self.assertGreater(result["files_verified"], 100)
            self.assertGreater(result["model_files"], 10)
            self.assertGreater(result["dataset_files"], 20)
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn(str(RAW_ROOT), json.dumps(manifest))
            self.assertEqual(manifest["korean_xstest_raw_rows"], "excluded_unresolved_license")
            self.assertEqual(manifest["collections"], ["dataset_collection", "model_collection"])
            self.assertEqual(len(manifest["source_adapters"]), 2)
            self.assertEqual(manifest["selected_adapter"]["sha256"], staging.ADAPTER_SHA256)
            self.assertEqual(manifest["selected_adapter"]["formula"], "0.75 * v7 + 0.25 * v8")
            card = (destination / "model_collection/README.md").read_text(encoding="utf-8")
            self.assertIn("license: cc-by-nc-4.0", card)
            self.assertNotIn("adapter/adapter_model.safetensors", card)
            self.assertIn("](code/release/REPRODUCE.md)", card)
            self.assertTrue((destination / "model_collection/LICENSE-MODEL").is_file())
            self.assertTrue((destination / "docs/REPRODUCE.md").is_file())
            self.assertTrue((destination / "LICENSE").is_file())
            review = destination / "model_collection/evidence/overrefusal/review_summary.en_it.json"
            review_text = review.read_text(encoding="utf-8")
            self.assertNotIn("ko-410", review_text)
            self.assertNotIn("ko-260", review_text)
            self.assertNotIn("review-052", review_text)
            self.assertNotIn("review-081", review_text)
            self.assertNotIn("review/review_summary.json", {entry["path"] for entry in manifest["files"]})
            replay = load_module("staged_replay_for_tests", destination / "code/release/replay_evidence.py")
            replay_result = replay.replay_all(staging_root=destination)
            self.assertEqual(replay_result["selected_model"], "merge_alpha_0.75")
            self.assertTrue(replay_result["staged_replay"])

    def test_missing_worktree_source_directory_fails_closed(self):
        # Catches silently publishing an incomplete code collection after a port omission.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worktree = root / "worktree"
            shutil.copytree(
                WORKTREE_ROOT,
                worktree,
                ignore=shutil.ignore_patterns(".git", ".release", ".public_staging", "__pycache__"),
            )
            shutil.rmtree(worktree / "data")
            with self.assertRaisesRegex(FileNotFoundError, r"required staging source directory.*data"):
                staging.build_staging(worktree, RAW_ROOT, root / "staging")
            self.assertFalse((root / "staging").exists())

    def test_missing_raw_source_directory_fails_closed_before_copying(self):
        # Catches silently dropping a required dataset/evidence tree from a partial raw checkout.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw"
            raw.mkdir()
            for source in RAW_ROOT.iterdir():
                if source.name == "issue10_generate":
                    continue
                (raw / source.name).symlink_to(source, target_is_directory=source.is_dir())
            with self.assertRaisesRegex(FileNotFoundError, r"required staging source directory.*issue10_generate"):
                staging.build_staging(WORKTREE_ROOT, raw, root / "staging")
            self.assertFalse((root / "staging").exists())

    def test_model_card_links_resolve_inside_uploaded_collection(self):
        # Catches parent-relative card links that escape the individually uploaded model repository.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            model_root = destination / "model_collection"
            card = (model_root / "README.md").read_text(encoding="utf-8")
            links = re.findall(r"\[[^]]+\]\(([^)]+)\)", card)
            self.assertIn("https://github.com/kendramoss/exsi-lexsi-hackathon", links)
            self.assertIn("https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75/blob/main/SHA256SUMS", links)
            self.assertIn("https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75/blob/main/manifest.json", links)
            relative_links = [link for link in links if not re.match(r"https?://", link)]
            self.assertTrue(
                {"code/release/REPRODUCE.md", "merge_provenance.json", "evidence/"}
                <= set(relative_links)
            )
            for link in relative_links:
                self.assertNotIn("..", Path(link).parts)
                self.assertTrue((model_root / link).exists(), link)

    def test_collection_manifests_describe_uploaded_collection_relative_files(self):
        # Catches copying aggregate staging manifests whose paths do not resolve in either uploaded repository.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            for collection in ("model_collection", "dataset_collection"):
                with self.subTest(collection=collection):
                    collection_root = destination / collection
                    manifest_path = collection_root / "manifest.json"
                    self.assertTrue(manifest_path.is_file())
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    self.assertTrue(manifest["files"])
                    for entry in manifest["files"]:
                        relative = entry["path"]
                        self.assertNotIn("..", Path(relative).parts)
                        self.assertFalse(relative.startswith(("model_collection/", "dataset_collection/")))
                        payload = collection_root / relative
                        self.assertTrue(payload.is_file(), relative)
                        self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), entry["sha256"])

    def test_both_collections_include_identical_license_and_notice_files(self):
        # Catches dataset-card license references missing from either independently uploaded collection.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            for name in ("NOTICE.md", "LICENSE-DECISION.md"):
                expected = (WORKTREE_ROOT / name).read_bytes()
                expected_hash = hashlib.sha256(expected).hexdigest()
                for collection in ("model_collection", "dataset_collection"):
                    with self.subTest(name=name, collection=collection):
                        payload = destination / collection / name
                        self.assertTrue(payload.is_file())
                        self.assertEqual(payload.read_bytes(), expected)
                        self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), expected_hash)
            self.assertEqual(staging.verify_staging(destination)["status"], "PASS")

    def test_dataset_card_disables_viewer_for_heterogeneous_evidence(self):
        # Catches enabling Hub tabular previews for packs that do not share a schema/config.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            text = (destination / "dataset_collection/README.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            parts = text.split("---\n", 2)
            metadata = yaml.safe_load(parts[1])
            self.assertEqual(metadata["viewer"], False)
            self.assertEqual(metadata["license"], "other")
            self.assertIn("heterogeneous", parts[2].lower())
            self.assertIn("download", parts[2].lower())

    def test_verifier_rejects_invalid_dataset_card_metadata(self):
        # Catches verifier acceptance of a missing or enabled viewer declaration after card edits.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            (destination / "dataset_collection/README.md").write_text("# Invalid metadata\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"dataset card metadata|viewer"):
                staging.verify_staging(destination)

    def test_publication_provenance_distinguishes_team_and_standalone_repositories(self):
        # Catches presenting the standalone preservation repository as the shared team submission.
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "staging"
            staging.build_staging(WORKTREE_ROOT, RAW_ROOT, destination)
            provenance_path = destination / "docs/PUBLICATION-RESULTS.json"
            self.assertTrue(provenance_path.is_file())
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(
                provenance["team_submission_repository"],
                "https://github.com/kendramoss/exsi-lexsi-hackathon",
            )
            self.assertIn("source/preservation only", provenance["standalone_github_role"])
            self.assertIn("not the team submission", provenance["standalone_github_role"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
