"""Offline investment-plan guardrails for NGN 200,000 budget and NGN 50,000 cap."""
import unittest
import datetime as dt
from crypto_oracle_scanner import investment_plan


class InvestmentPlanTests(unittest.TestCase):
    def test_not_included_for_wait(self):
        self.assertEqual(investment_plan({"base_token_price_usd": 1}, "WAIT AND VERIFY"), "")

    def test_missing_price(self):
        plan = investment_plan({}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("Total speculative budget: NGN 200,000", plan)
        self.assertIn("Illustrative maximum allocation: NGN 20,000", plan)
        self.assertIn("NGN 20,000", plan)
        self.assertIn("NGN 2,000", plan)
        self.assertIn("UNAVAILABLE", plan)

    def test_stale_price_has_no_targets(self):
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
        plan = investment_plan({"base_token_price_usd": 2.0, "observed_at": old}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("UNAVAILABLE", plan)
        self.assertNotIn("Take-profit 1:", plan)

    def test_price_targets(self):
        plan = investment_plan({"base_token_price_usd": 2.0, "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("USD 2", plan)
        self.assertIn("Entry/stop/targets: UNAVAILABLE", plan)
        self.assertNotIn("USD 1.8", plan)
        self.assertIn("USD order amount: UNAVAILABLE", plan)
        self.assertIn("Executable quote/slippage: NOT VERIFIED", plan)


if __name__ == "__main__":
    unittest.main()
