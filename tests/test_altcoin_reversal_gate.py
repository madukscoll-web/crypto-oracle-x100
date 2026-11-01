"""Gate adapter unit tests without live network access."""
import unittest
from altcoin_reversal_gate import gate_candles, research_gate_pair


def rows():
    return [[str(1700000000 + i * 86400), "1000", "101", "102", "99", "100", "10"]
            for i in range(60)]


class FakeGate:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get(self, path, query=None):
        self.calls.append((path, query))
        return self.data


class GateReversalTests(unittest.TestCase):
    def test_closed_candles_parsed(self):
        self.assertEqual(len(gate_candles(rows(), interval_seconds=86400, now=1800000000)), 60)

    def test_current_candle_excluded(self):
        self.assertEqual(len(gate_candles(rows(), interval_seconds=86400,
                                          now=1700000000 + 59 * 86400 + 100)), 59)

    def test_duplicate_timestamp_rejected(self):
        data = rows()
        data[-1][0] = data[-2][0]
        with self.assertRaises(ValueError):
            gate_candles(data, interval_seconds=86400, now=1800000000)

    def test_gate_public_endpoint_only(self):
        gate = FakeGate(rows())
        result = research_gate_pair(gate, "LINK_USDT", now=1800000000)
        self.assertFalse(result["buy_authorized"])
        self.assertEqual(gate.calls[0][0], "/spot/candlesticks")

    def test_stablecoin_excluded_before_api_call(self):
        gate = FakeGate(rows())
        with self.assertRaises(ValueError):
            research_gate_pair(gate, "USDC_USDT", now=1800000000)
        self.assertFalse(gate.calls)


if __name__ == "__main__":
    unittest.main()
