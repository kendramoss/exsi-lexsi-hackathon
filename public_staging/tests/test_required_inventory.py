"""Lightweight fail-closed preflight tests: no weights or full bundles are copied."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_staging import RAW_ROOT, WORKTREE_ROOT, staging


def shadow_without(source, destination, omitted):
    """Link untouched trees; expand only ancestors of the deliberately omitted files."""
    destination.mkdir()
    for child in source.iterdir():
        matching = [p for p in omitted if p.parts[0] == child.name]
        if not matching:
            (destination / child.name).symlink_to(child, target_is_directory=child.is_dir())
        elif any(len(p.parts) == 1 for p in matching):
            continue
        else:
            shadow_without(child, destination / child.name, [Path(*p.parts[1:]) for p in matching])


class RequiredInventoryTests(unittest.TestCase):
    def preflight_rejects(self, raw, worktree, output, error, message):
        # Hashing weights is unrelated to tree inventory; copying must never begin on bad input.
        with patch.object(staging, "verify_selected_adapter"), patch.object(
            staging.shutil, "copyfile", side_effect=AssertionError("copy began before inventory validation")
        ), self.assertRaisesRegex(error, message):
            staging.build_staging(worktree, raw, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob(f".{output.name}.tmp-*")))

    def test_empty_required_dataset_tree_is_rejected_before_copying(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw"
            shadow_without(RAW_ROOT, raw, [Path("issue10_generate")])
            (raw / "issue10_generate").mkdir()
            self.preflight_rejects(raw, WORKTREE_ROOT, root / "staging", ValueError,
                                   "no eligible.*issue10_generate")

    def test_required_code_tree_with_only_excluded_suffixes_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worktree = root / "worktree"
            shadow_without(WORKTREE_ROOT, worktree, [Path("data")])
            (worktree / "data").mkdir()
            (worktree / "data/ignored.pyc").write_bytes(b"excluded cache")
            (worktree / "data/notes.csv").write_text("excluded suffix")
            self.preflight_rejects(RAW_ROOT, worktree, root / "staging", ValueError, "no eligible.*data")

    def test_mandatory_source_label_and_manifest_omissions_fail_before_copying(self):
        # A nonempty tree (e.g. a build script alone) is not proof its advertised pack exists.
        required = [
            "issue10_generate/issue10_generated_source.jsonl",
            "issue10_generate/issue10_generated_labels.json", "issue10_generate/MANIFEST.json",
            "semantic_contrast/packs_v2/train_source.jsonl", "semantic_contrast/packs_v2/dev_labels.json",
            "semantic_contrast/packs_v2/frozen_test_FREEZE.json", "semantic_contrast/packs_v2/MANIFEST.json",
            "v8_data/packs/new_independent_frozen_test_source.jsonl", "v8_data/packs/train_labels.json",
            "v8_data/packs/new_independent_frozen_test_FREEZE.json", "v8_data/packs/MANIFEST.json",
            "resolution_expand/pack/dev_source.jsonl", "resolution_expand/pack/dev_followup_labels.json",
            "resolution_expand/pack/manifest.json", "issue8_arabic/pack/evaluation_source.jsonl",
            "issue8_arabic/pack/evaluation_labels.json", "issue8_arabic/pack/manifest.json",
            "data_v6/train_source.jsonl", "data_v6/devwide_labels.json", "data_v6/manifest.json",
            "results/v7/evtune-next-inputs/input_manifest.json",
            "results/v7/evtune-next-inputs/inputs/v6_semantic/curated/sft_alpaca.jsonl",
            "results/v8/evtune-v8-inputs/input_manifest.json",
            "results/v8/evtune-v8-inputs/inputs/v8_targeted_two_turn/curated/sft_alpaca.jsonl",
        ]
        for relative in required:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                raw = root / "raw"
                shadow_without(RAW_ROOT, raw, [Path(relative)])
                self.preflight_rejects(raw, WORKTREE_ROOT, root / "staging", FileNotFoundError,
                                       "required staging source file missing.*" + Path(relative).name)


if __name__ == "__main__":
    unittest.main()
