import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_kit  # noqa: E402


class KitTests(unittest.TestCase):
    def test_all_checks_pass(self):
        total, results = check_kit.run()
        self.assertTrue(120 <= total <= 145, total)
        for name, errors in results.items():
            self.assertEqual(errors, [], name)

    def test_timing_detects_gap(self):
        data = check_kit.load_scenes()
        data["scenes"][1]["start"] += 1
        self.assertTrue(check_kit.check_timing(data))

    def test_word_range_detects_short_script(self):
        data = check_kit.load_scenes()
        data["scenes"][3]["narration"] = "Short."
        self.assertTrue(check_kit.check_words(data))


if __name__ == "__main__":
    unittest.main()
