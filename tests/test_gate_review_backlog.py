import unittest
from gate_review_backlog import summarize


class ReviewBacklogTests(unittest.TestCase):
    def test_empty_registry_is_explicitly_blocked(self):
        r = summarize({"version": 1, "tokens": {}}, None)
        self.assertTrue(r["review_registry_empty"])
        self.assertTrue(r["review_required"])
        self.assertFalse(r["buy_authorized"])
        self.assertFalse(r["telegram_eligible"])
        self.assertFalse(r["orders_allowed"])

    def test_blockers_counted_without_approvals(self):
        r = summarize({"tokens": {"example": {"reviewer": "test"}}},
                      {"candidates": [{"blockers": ["missing supply", "missing holders"]},
                                      {"blockers": ["missing supply"]}]})
        self.assertEqual(r["candidate_blocker_counts"]["missing supply"], 2)
        self.assertEqual(r["candidate_blocker_counts"]["missing holders"], 1)
        self.assertFalse(r["buy_authorized"])

    def test_invalid_registry_fails(self):
        with self.assertRaises(ValueError):
            summarize({"tokens": []}, None)


if __name__ == "__main__":
    unittest.main()
