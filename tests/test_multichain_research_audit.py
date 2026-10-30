import unittest
from multichain_research_audit import audit

class AuditTests(unittest.TestCase):
    def test_fail_closed(self):
        result = audit({"mode": "READ_ONLY_RESEARCH",
                        "selected": [{"network": "solana"}, {"network": "eth"}],
                        "failures": [{"network": "bsc"}], "deferred": 3})
        self.assertEqual(result["selected_total"], 2)
        self.assertEqual(result["discovery_failure_count"], 1)
        self.assertFalse(result["buy_authorized"])
        self.assertFalse(result["telegram_eligible"])
        self.assertEqual(result["verified_buy_count"], 0)
    def test_reject_wrong_report(self):
        with self.assertRaises(ValueError):
            audit({"mode": "TRADING", "selected": []})

if __name__ == "__main__":
    unittest.main()
