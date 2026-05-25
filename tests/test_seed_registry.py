from __future__ import annotations

import unittest


class SeedRegistryTest(unittest.TestCase):
    def test_lists_registered_seed_extractors(self) -> None:
        from scripts.seed_registry import registered_seed_extractors

        registry = registered_seed_extractors()

        self.assertIn("meiji_2027_schedule", registry)
        self.assertIn("waseda_2027_official", registry)
        self.assertEqual(registry["meiji_2027_schedule"]["expected_path"], "quality_baselines/meiji_2027_schedule.expected.json")
        self.assertEqual(registry["waseda_2027_official"]["source_candidates"][0], "data/uploads/waseda_2027_official.pdf")

    def test_selects_seed_extractor_for_matching_source_text(self) -> None:
        from scripts.seed_registry import seed_for_source

        seed = seed_for_source("明治大学", "2027", "明治大学 2027年度外国人留学生入学試験 試験科目・日程等一覧")

        self.assertIsNotNone(seed)
        self.assertEqual(seed["stem"], "meiji_2027_schedule")

    def test_does_not_select_seed_for_wrong_university(self) -> None:
        from scripts.seed_registry import seed_for_source

        seed = seed_for_source("明治大学", "2027", "早稲田大学 2027年度 外国学生")

        self.assertIsNone(seed)


if __name__ == "__main__":
    unittest.main()
