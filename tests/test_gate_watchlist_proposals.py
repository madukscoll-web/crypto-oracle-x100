import datetime as dt
import unittest

from gate_watchlist_proposals import make_proposal, render_proposal

VALID = {
    "decision": "BUY WATCHLIST — RESEARCH ONLY",
    "pair": "ABC_USDT",
    "turnover": 500000,
    "change_24h": 5.0,
    "orderbook": {"bid": 1.99, "ask": 2.0, "spread_pct": 0.501253,
                  "bid_depth_usdt": 10000, "ask_depth_usdt": 10000},
}
NOW = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)

class ProposalTests(unittest.TestCase):
    def test_research_proposal_never_approves_order(self):
        p = make_proposal(VALID, NOW)
        self.assertEqual(p["status"], "WATCHLIST_ONLY")
        self.assertFalse(p["approval_enabled"])
        self.assertIsNone(p["order_amount_usdt"])
        self.assertIn("No trade will be placed", render_proposal(p))
    def test_wait_rejected(self):
        self.assertIsNone(make_proposal({**VALID, "decision": "WAIT / VERIFY"}, NOW))
    def test_bad_depth_rejected(self):
        c = {**VALID, "orderbook": {**VALID["orderbook"], "ask_depth_usdt": 20}}
        self.assertIsNone(make_proposal(c, NOW))
    def test_invalid_pair_rejected(self):
        self.assertIsNone(make_proposal({**VALID, "pair": "ABC/USDT"}, NOW))
    def test_expiry(self):
        p = make_proposal(VALID, NOW)
        self.assertEqual((dt.datetime.fromisoformat(p["expires_at"]) - NOW).total_seconds(), 120)
    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            make_proposal(VALID, dt.datetime(2026, 10, 20))

if __name__ == "__main__":
    unittest.main()
