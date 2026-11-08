import unittest
from datetime import datetime, timedelta, timezone
from atl_recovery import assess_recovery

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.candles = []
        for i in range(30):
            low = 10 if i < 25 else 11
            close = 12 if i < 29 else 14
            self.candles.append(dict(at=(self.start + timedelta(hours=i)).isoformat(),
                 low=low, high=15, close=close, volume=100 if i < 29 else 200,
                 closed=True))
        self.kw = dict(comparable=True, venue_verified=True,
                       now=self.start + timedelta(hours=30))
    def test_trigger_is_not_buy(self):
        result = assess_recovery(self.candles, **self.kw)
        self.assertEqual(result["status"], "TECHNICAL WATCH")
        self.assertFalse(result["buy_approved"])
    def test_missing_and_unclosed(self):
        self.assertEqual(assess_recovery(self.candles[:20], **self.kw)["status"], "INSUFFICIENT EVIDENCE")
        self.candles[-1]["closed"] = False
        self.assertEqual(assess_recovery(self.candles, **self.kw)["status"], "INSUFFICIENT EVIDENCE")
    def test_gap_and_stale(self):
        self.candles[10]["at"] = (self.start + timedelta(hours=10, minutes=10)).isoformat()
        self.assertEqual(assess_recovery(self.candles, **self.kw)["reason"], "CANDLE_GAP_OR_WRONG_TIMEFRAME")
    def test_unverified_venue(self):
        self.assertEqual(assess_recovery(self.candles, comparable=True, now=self.kw["now"])["status"], "INSUFFICIENT EVIDENCE")

if __name__ == "__main__":
    unittest.main()

