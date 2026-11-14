"""Guards the documented lightweight environment against drift."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CleanEnvironmentDocs(unittest.TestCase):
    def test_declared_dependencies_are_lightweight_and_documented(self):
        reqs = (ROOT / "requirements-dev.txt").read_text().splitlines()
        names = {re.split(r"[<>=!~ ]", r, 1)[0].lower()
                 for r in reqs if r.strip() and not r.startswith("#")}
        self.assertEqual(names, {"jsonschema", "pyyaml", "numpy", "safetensors"})
        doc = (ROOT / "docs" / "offline-checks.md").read_text().lower()
        for n in names:
            self.assertIn(n, doc)

    def test_doc_lists_verified_suites(self):
        doc = (ROOT / "docs" / "offline-checks.md").read_text()
        for suite in ("scripts/tests", "demo/tests", "teacher/tests", "public_staging/tests"):
            self.assertIn(f"discover -s {suite}", doc)


if __name__ == "__main__":
    unittest.main()
