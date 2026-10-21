import unittest
import valuation_scenarios as v


class ValuationTests(unittest.TestCase):
    def test_constant_supply_100x_requires_100x_cap(self):
        x = v.scenario(1000000, 100000000, 100000000, 100)
        self.assertEqual(x["required_future_market_cap_usd"], 100000000)
        self.assertEqual(x["probability"], "NOT STATISTICALLY ESTABLISHED")

    def test_doubling_supply_requires_200x_cap(self):
        x = v.scenario(1000000, 100000000, 200000000, 100)
        self.assertEqual(x["required_future_market_cap_usd"], 200000000)

    def test_missing_supply_does_not_guess(self):
        self.assertEqual(v.scenario(1000000, None, None, 100)["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
