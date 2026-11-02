import unittest
from altcoin_reversal_alerts import select_watches, format_watch

class AlertPolicyTests(unittest.TestCase):
    def sample(self):
        return {"buy_authorized": False, "orders_allowed": False, "results": [{
            "pair": "LINK_USDT", "status": "RESEARCH_ONLY",
            "buy_authorized": False, "orders_allowed": False,
            "research": {"classification": "EARLY REVERSAL WATCH",
                "buy_authorized": False, "orders_allowed": False,
                "observed_at": "2026-11-02T12:00:00+00:00",
                "interval": "1d", "source": "Gate Spot public API v4",
                "entry_trigger": 12.0, "invalidation": 9.0,
                "metrics": {"close": 10.0, "volume_ratio": 1.2}}
        }]}
    def test_watch_allowed_not_buy(self):
        rows = select_watches(self.sample())
        self.assertEqual(len(rows), 1)
        self.assertIn("NOT APPROVED FOR PURCHASE", format_watch(rows[0]))
    def test_reject_unknown_and_discard(self):
        for classification in ("INSUFFICIENT EVIDENCE", "DISCARD", "BUY CANDIDATE — MANUAL REVIEW"):
            report = self.sample()
            report["results"][0]["research"]["classification"] = classification
            self.assertEqual(select_watches(report), [])
    def test_reject_unsafe_evidence(self):
        report = self.sample()
        report["results"][0]["research"]["buy_authorized"] = True
        self.assertEqual(select_watches(report), [])
    def test_reject_invalid_reference(self):
        report = self.sample()
        report["results"][0]["research"]["invalidation"] = 11.0
        self.assertEqual(select_watches(report), [])
    def test_reject_untrusted_root(self):
        report = self.sample()
        report["buy_authorized"] = True
        with self.assertRaises(ValueError):
            select_watches(report)

if __name__ == "__main__":
    unittest.main()
