"""Walk-forward evaluation tests."""
import unittest
from altcoin_reversal_backtest import walk_forward


def candles(n=85):
    rows = []
    for i in range(n):
        close = 100 + i * 0.1
        rows.append(dict(timestamp=i + 1, open=close, high=close + 1,
                         low=close - 1, close=close, volume=1000, closed=True))
    return rows


class BacktestTests(unittest.TestCase):
    def test_no_buy_authorization(self):
        r = walk_forward("LINK/USDT", candles(), source="test", horizon=10)
        self.assertFalse(r["buy_authorized"])
        self.assertEqual(r["evaluated_windows"], 21)

    def test_short_history_rejected(self):
        with self.assertRaises(ValueError):
            walk_forward("LINK/USDT", candles(60), source="test", horizon=10)

    def test_invalid_costs_rejected(self):
        with self.assertRaises(ValueError):
            walk_forward("LINK/USDT", candles(), source="test", fee_bps=-1)

    def test_no_future_candles_used_for_signal(self):
        rows = candles()
        a = walk_forward("LINK/USDT", rows, source="test", horizon=10)
        rows[-1]["close"] = 200
        rows[-1]["high"] = 201
        b = walk_forward("LINK/USDT", rows, source="test", horizon=10)
        self.assertEqual(a["observations"][0:1], b["observations"][0:1])


if __name__ == "__main__":
    unittest.main()
