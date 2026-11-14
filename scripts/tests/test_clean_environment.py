"""Guards the documented lightweight environment against drift."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CleanEnvironmentDocs(unittest.TestCase):
    def test_declared_dependencies_are_lightweight_and_documented(self):
        reqs = (ROOT / "requirements-dev.txt").read_text().splitlines()
        names = {re.split(r"[<>=!~ ]", r, maxsplit=1)[0].lower()
                 for r in reqs if r.strip() and not r.startswith("#")}
        self.assertEqual(names, {"jsonschema", "pyyaml", "numpy", "safetensors"})
        doc = (ROOT / "docs" / "offline-checks.md").read_text().lower()
        for n in names:
            self.assertIn(n, doc)

    def test_doc_lists_verified_suites(self):
        doc = (ROOT / "docs" / "offline-checks.md").read_text()
        for suite in ("scripts/tests", "demo/tests", "teacher/tests", "public_staging/tests"):
            self.assertIn(f"discover -s {suite}", doc)

    def test_checkout_only_section_does_not_require_raw_staging_artifacts(self):
        doc = (ROOT / "docs" / "offline-checks.md").read_text()
        section = doc.split("## Checks requiring only this checkout", 1)[1].split("## Explicit raw-evidence demo integration", 1)[0]
        commands = [line for line in section.splitlines() if "discover -s public_staging/tests" in line]
        self.assertTrue(commands)
        for command in commands:
            self.assertIn("-k ", command)
        self.assertTrue(any("korean_rows" in line for line in commands))
        self.assertTrue(any("wrong_selected_adapter" in line for line in commands))

    def test_clean_install_record_discloses_staging_evidence_dependency(self):
        doc = (ROOT / "docs" / "offline-checks.md").read_text()
        record = doc.split("### Clean-install record", 1)[1].split("## Checks requiring only this checkout", 1)[0]
        self.assertIn("existing raw-evidence", record)
        self.assertNotIn("No raw-replay or build checks were run", record)


if __name__ == "__main__":
    unittest.main()
