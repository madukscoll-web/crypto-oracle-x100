"""Offline investment-plan guardrails for the authorized NGN 50,000 budget."""
import unittest
from crypto_oracle_scanner import investment_plan


class InvestmentPlanTests(unittest.TestCase):
    def test_not_included_for_wait(self):
        self.assertEqual(investment_plan({"base_token_price_usd": 1}, "WAIT AND VERIFY"), "")

    def test_missing_price(self):
        plan = investment_plan({}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("NGN 50,000", plan)
        self.assertIn("NGN 500", plan)
        self.assertIn("NGN 50", plan)
        self.assertIn("UNAVAILABLE", plan)

    def test_price_targets(self):
        plan = investment_plan({"base_token_price_usd": 2.0}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("USD 2", plan)
        self.assertIn("USD 1.8", plan)
        self.assertIn("USD 2.4", plan)
        self.assertIn("USD 3", plan)
        self.assertIn("USD order amount: UNAVAILABLE", plan)


if __name__ == "__main__":
    unittest.main()
