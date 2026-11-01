"""No-network CLI regression tests."""
import unittest
from altcoin_reversal_cli import run


def fake_fetch(url):
    if "/spot/currency_pairs/LINK_USDT" in url:
        return dict(id="LINK_USDT", base="LINK", quote="USDT", type="normal",
                    trade_status="tradable", st_tag=False, buy_start=1, sell_start=1)
    if "/spot/candlesticks" in url:
        return [[str(1700000000 + i * 86400), "1000", str(100 + i * .1),
                 str(101 + i * .1), str(99 + i * .1), str(100 + i * .1), "10"]
                for i in range(100)]
    raise AssertionError("Unexpected public endpoint: " + url)


class ReversalCLITests(unittest.TestCase):
    def test_mocked_gate_pair_stays_research_only(self):
        result = run(["LINK_USDT"], fetch=fake_fetch, now=1700000000 + 101 * 86400)
        row = result["results"][0]
        self.assertEqual(row["status"], "RESEARCH_ONLY")
        self.assertEqual(row["candle_count"], 100)
        self.assertFalse(row["research"]["buy_authorized"])
        self.assertFalse(row["backtest"]["buy_authorized"])

    def test_stablecoin_rejected_without_request(self):
        def forbidden(_):
            raise AssertionError("No API calls expected")
        result = run(["USDC_USDT"], fetch=forbidden, now=1700000000 + 101 * 86400)
        self.assertEqual(result["results"][0]["status"], "UNAVAILABLE")

    def test_missing_metadata_fails_closed(self):
        result = run(["ONDO_USDT"], fetch=lambda _: {}, now=1700000000 + 101 * 86400)
        self.assertEqual(result["results"][0]["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
