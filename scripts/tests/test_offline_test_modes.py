"""Exercise demo test discovery without the author's raw evidence directory."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class OfflineDemoTestModes(unittest.TestCase):
    def run_demo_tests(self, raw_root=None):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("EVTUNE_DEMO_RAW_ROOT", None)
        if raw_root is not None:
            env["EVTUNE_DEMO_RAW_ROOT"] = str(raw_root)
        return subprocess.run(
            [sys.executable, "-I", "-B", "-m", "unittest", "discover",
             "-s", str(ROOT / "demo/tests"), "-p", "test_merged_demo.py", "-v"],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )

    def test_default_runs_pure_checks_and_explicitly_skips_evidence_checks(self):
        # Raw regeneration must not be a prerequisite for payload tamper checks.
        result = self.run_demo_tests()
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        for name in (
            "test_raw_output_tampering_is_rejected",
            "test_backend_mixing_is_rejected",
            "test_headline_score_tampering_is_rejected",
            "test_written_payload_is_machine_verifiable",
        ):
            self.assertRegex(output, name + r" .* \.\.\. ok")
        self.assertIn("skipped=2", output)
        self.assertIn("EVTUNE_DEMO_RAW_ROOT", output)

    def test_explicit_empty_evidence_setting_fails_not_skips(self):
        result = self.run_demo_tests("")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("EVTUNE_DEMO_RAW_ROOT", output)
        self.assertIn("not an empty value", output)
        self.assertNotIn("skipped=", output)

    def test_explicit_missing_evidence_fails_clearly_not_skips(self):
        # Opting into source verification cannot turn missing inputs into a green skip.
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_demo_tests(Path(temporary))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("EVTUNE_DEMO_RAW_ROOT", output)
        self.assertIn("missing required demo evidence", output)
        self.assertIn("selection.json", output)
        self.assertNotIn("skipped=", output)
        self.assertRegex(output, r"test_raw_output_tampering_is_rejected .* \.\.\. ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
