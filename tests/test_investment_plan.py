"""Offline investment-plan formatting and guardrails."""
import os
import unittest
from unittest.mock import patch
from crypto_oracle_scanner import investment_plan


class InvestmentPlanTests(unittest.TestCase):
    def test_not_included_for_wait(self):
        self.assertEqual(investment_plan({"base_token_price_usd": 1}, "WAIT AND VERIFY"), "")

    def test_no_price_does_not_invent_entry(self):
        with patch.dict(os.environ, {"ORACLE_PORTFOLIO_BUDGET_USD": "1000"}):
            plan = investment_plan({}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("UNAVAILABLE", plan)
        self.assertIn("$10.00", plan)

    def test_no_budget_does_not_invent_amount(self):
        with patch.dict(os.environ, {"ORACLE_PORTFOLIO_BUDGET_USD": ""}):
            plan = investment_plan({"base_token_price_usd": 0.05}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("NOT SET", plan)
        self.assertIn("0.06", plan)
        self.assertIn("0.075", plan)

    def test_positive_budget_and_price(self):
        with patch.dict(os.environ, {"ORACLE_PORTFOLIO_BUDGET_USD": "2000"}):
            plan = investment_plan({"base_token_price_usd": 2.0}, "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("$20.00", plan)
        self.assertIn("$1.8", plan)
        self.assertIn("$2.4", plan)
        self.assertIn("$3", plan)


if __name__ == "__main__":
    unittest.main()
