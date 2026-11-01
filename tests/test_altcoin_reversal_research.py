"""Regression tests for read-only altcoin reversal research."""
import unittest
from altcoin_reversal_research import analyze, eligible_symbol


def candles():
    rows = []
    for i in range(55):
        close = 100 + i * 0.15
        rows.append(dict(timestamp=f"2026-01-{i+1:03d}", open=close,
                         high=close + 1, low=close - 1, close=close,
                         volume=1000, closed=True))
    return rows


class ReversalTests(unittest.TestCase):
    def scan(self, symbol="LINK/USDT", rows=None):
        return analyze(symbol, candles() if rows is None else rows,
                       source="verified exchange candles", observed_at="2026-11-01T00:00:00Z")

    def test_excludes_stablecoins_and_leverage(self):
        for symbol in ("USDT/USDC", "USDC_USDT", "DAI/USDT", "BTC3L/USDT", "ETH5S_USDT"):
            self.assertFalse(eligible_symbol(symbol))
            self.assertEqual(self.scan(symbol)["classification"], "INSUFFICIENT EVIDENCE")

    def test_read_only(self):
        r = self.scan()
        self.assertFalse(r["buy_authorized"])
        self.assertFalse(r["orders_allowed"])
        self.assertFalse(r["telegram_eligible"])

    def test_missing_candles_fail_closed(self):
        self.assertEqual(self.scan(rows=candles()[:10])["classification"], "INSUFFICIENT EVIDENCE")

    def test_unclosed_candle_fails(self):
        rows = candles()
        rows[-1]["closed"] = False
        self.assertEqual(self.scan(rows=rows)["classification"], "INSUFFICIENT EVIDENCE")

    def test_out_of_order_fails(self):
        rows = candles()
        rows[-1]["timestamp"] = rows[-2]["timestamp"]
        self.assertEqual(self.scan(rows=rows)["classification"], "INSUFFICIENT EVIDENCE")

    def test_breakout_watch_never_buy(self):
        rows = candles()
        rows[-1]["open"] = 108
        rows[-1]["close"] = 115
        rows[-1]["high"] = 116
        rows[-1]["low"] = 107
        rows[-1]["volume"] = 2500
        r = self.scan(rows=rows)
        self.assertIn(r["classification"], ("TECHNICAL REVERSAL WATCH", "EARLY REVERSAL WATCH", "INSUFFICIENT EVIDENCE"))
        self.assertFalse(r["buy_authorized"])


if __name__ == "__main__":
    unittest.main()
