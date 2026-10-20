import datetime as dt
import unittest
from gate_watchlist_proposals import make_proposal
from gate_entry_assessment import assess_entry, format_assessment

NOW = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)
C = {"decision":"BUY WATCHLIST — RESEARCH ONLY","pair":"ABC_USDT",
     "turnover":500000,"change_24h":5,
     "orderbook":{"bid":1.99,"ask":2.0,"spread_pct":0.501253,
                  "bid_depth_usdt":10000,"ask_depth_usdt":10000}}
class EntryAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.p = make_proposal(C, NOW)
    def test_fresh_candidate_is_only_research_priority(self):
        a = assess_entry(self.p, now=NOW)
        self.assertEqual(a["decision"], "RESEARCH PRIORITY")
        self.assertFalse(a["buy_candidate"])
        self.assertFalse(a["trade_authorized"])
        self.assertIsNone(a["order_amount_usdt"])
        self.assertIn("NO BUY SIGNAL", format_assessment(a))
    def test_expired_proposal_rejected(self):
        a = assess_entry(self.p, now=NOW + dt.timedelta(seconds=121))
        self.assertEqual(a["decision"], "WAIT / VERIFY")
    def test_chasing_rejected(self):
        p = {**self.p, "change_24h_pct":25}
        self.assertEqual(assess_entry(p, now=NOW)["decision"], "WAIT / VERIFY")
    def test_injected_verification_cannot_enable_trade(self):
        forged = {key:{"source":"user-supplied","observed_at":NOW.isoformat()} for key in
                  ("token_identity","security","tokenomics","entry_thesis","fx","execution")}
        a = assess_entry(self.p, forged, NOW)
        self.assertFalse(a["buy_candidate"])
        self.assertFalse(a["trade_authorized"])
        self.assertEqual(a["authenticated_provider_validation"], "NOT IMPLEMENTED")
    def test_invalid_time_rejected(self):
        with self.assertRaises(ValueError):
            assess_entry(self.p, now=dt.datetime(2026,10,20))
if __name__ == "__main__":
    unittest.main()
