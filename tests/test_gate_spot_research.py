import unittest
from gate_spot_research import eligible_tickers, orderbook_evidence, assess_spot_candidate, build_watchlist

PAIRS = [{"id":"ABC_USDT","quote":"USDT","trade_status":"tradable"},
         {"id":"HALT_USDT","quote":"USDT","trade_status":"halted"}]
TICKERS = [{"currency_pair":"ABC_USDT","last":"2","quote_volume":"500000","change_percentage":"5"},
           {"currency_pair":"HALT_USDT","last":"2","quote_volume":"900000","change_percentage":"1"}]
BOOK = {"bids":[["1.99","5000"]],"asks":[["2.00","5000"]]}

class GateResearchTests(unittest.TestCase):
    def test_only_tradable(self):
        self.assertEqual([x["pair"] for x in eligible_tickers(TICKERS, PAIRS)], ["ABC_USDT"])
    def test_orderbook(self):
        x = orderbook_evidence(BOOK)
        self.assertGreater(x["bid_depth_usdt"], 5000)
        self.assertLess(x["spread_pct"], 0.8)
    def test_no_book(self):
        self.assertIsNone(orderbook_evidence({"bids":[],"asks":[]}))
    def test_watchlist_not_buy(self):
        t = eligible_tickers(TICKERS, PAIRS)[0]
        decision, reason, _ = assess_spot_candidate(t, BOOK)
        self.assertEqual(decision, "BUY WATCHLIST — RESEARCH ONLY")
        self.assertIn("UNVERIFIED", reason)
    def test_no_unapproved_order(self):
        result = build_watchlist(TICKERS, PAIRS, lambda pair: BOOK)
        self.assertEqual(len(result), 1)
        self.assertNotIn("BUY CANDIDATE", result[0]["decision"])
    def test_crossed_book_rejected(self):
        self.assertIsNone(orderbook_evidence({"bids":[["3","100"]],"asks":[["2","100"]]}))

if __name__ == "__main__":
    unittest.main()
