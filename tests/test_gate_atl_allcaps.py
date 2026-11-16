import unittest
from gate_atl_allcaps import market_cap_bucket, screen


class GateAllCapsATLTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual([market_cap_bucket(x) for x in
                          (1, 10000000, 200000000, 1000000001, None)],
                         ["MICRO_CAP", "LOW_CAP", "MID_CAP", "HIGH_CAP", "UNVERIFIED"])

    def test_exact_identity_and_threshold(self):
        pairs = [{"base": s, "quote": "USDT", "id": s + "_USDT",
                  "trade_status": "tradable", "type": "normal", "st_tag": False}
                 for s in ("MICRO", "LOW", "MID", "HIGH", "WRONG")]
        tickers = [{"currency_pair": s + "_USDT", "last": "1.2"}
                   for s in ("MICRO", "LOW", "MID", "HIGH", "WRONG")]
        assets = [{"id": s.lower(), "atl": "1", "atl_date": "2025-01-01",
                   "market_cap": cap} for s, cap in
                  (("MICRO", 100), ("LOW", 10000000),
                   ("MID", 200000000), ("HIGH", 2000000000), ("WRONG", 100))]
        identities = {s: s.lower() for s in ("MICRO", "LOW", "MID", "HIGH")}
        result = screen(pairs, tickers, assets, identities)
        self.assertEqual(len(result["candidates"]), 4)
        self.assertEqual(result["counts"]["identity_unresolved"], 1)
        self.assertEqual({x["cap_category"] for x in result["candidates"]},
                         {"MICRO_CAP", "LOW_CAP", "MID_CAP", "HIGH_CAP"})
        self.assertTrue(all(not x["lifetime_verified"] and
                            not x["telegram_eligible"] and not x["buy_authorized"]
                            for x in result["candidates"]))
        self.assertFalse(result["orders_allowed"])

    def test_invalid_prices_and_over_threshold(self):
        pair = [{"base": "A", "quote": "USDT", "id": "A_USDT",
                 "trade_status": "tradable", "type": "normal"}]
        asset = [{"id": "a", "atl": "1", "atl_date": "2025-01-01"}]
        for price, expected in (("1.201", 0), ("0.9", 0), ("NaN", 0), ("1.19", 1)):
            with self.subTest(price=price):
                report = screen(pair, [{"currency_pair": "A_USDT", "last": price}],
                                asset, {"A": "a"})
                self.assertEqual(len(report["candidates"]), expected)


if __name__ == "__main__":
    unittest.main()
