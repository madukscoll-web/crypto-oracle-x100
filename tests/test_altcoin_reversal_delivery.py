import unittest
from altcoin_reversal_delivery import deliver

class DeliveryTests(unittest.TestCase):
    def report(self):
        return {"buy_authorized": False, "results": [{
            "pair": "LINK_USDT", "status": "RESEARCH_ONLY", "buy_authorized": False,
            "orders_allowed": False, "latest_closed_candle": 1700000000,
            "research": {"classification": "EARLY REVERSAL WATCH", "buy_authorized": False,
                "orders_allowed": False, "observed_at": "2026-11-02T00:00:00Z",
                "interval": "1d", "source": "Gate Spot public API v4",
                "entry_trigger": 12.0, "invalidation": 9.0,
                "metrics": {"close": 10.0, "volume_ratio": 1.2}}
        }]}
    def test_delivery_then_dedup(self):
        sent = []
        state, summary = deliver(self.report(), {"delivered": {}}, sender=sent.append)
        self.assertEqual(summary["alerts_delivered"], 1)
        _, summary2 = deliver(self.report(), state, sender=sent.append)
        self.assertEqual(summary2["alerts_delivered"], 0)
        self.assertEqual(len(sent), 1)
    def test_failure_propagates(self):
        def fail(_):
            raise RuntimeError("delivery failure")
        with self.assertRaises(RuntimeError):
            deliver(self.report(), {"delivered": {}}, sender=fail)
    def test_rejected_not_sent(self):
        report = self.report()
        report["results"][0]["research"]["classification"] = "DISCARD"
        sent = []
        _, summary = deliver(report, {"delivered": {}}, sender=sent.append)
        self.assertEqual(summary["alerts_delivered"], 0)
        self.assertFalse(sent)

if __name__ == "__main__":
    unittest.main()
