"""Opt-in research notification tests: never relax BUY evidence."""
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner


class ResearchNotificationTests(unittest.TestCase):
    def candidate(self):
        return dict(network="base", token_address="0x123", address="0x456",
                    token_identity_status="VERIFIED", risk_category="WAIT / VERIFY",
                    liquidity=50000.0, volume=10000.0, trades=50, buy_share=0.6,
                    change_h1=2.0, change_h24=4.0)

    def test_opt_in_wait_can_be_reported_without_becoming_buy(self):
        with patch.dict("os.environ", {"ORACLE_RESEARCH_ALERTS": "true"}), \
             patch.object(scanner, "decision_summary", return_value=("WAIT AND VERIFY", "review")), \
             patch.object(scanner.hourly_evidence, "adverse", return_value=False):
            item = self.candidate()
            self.assertTrue(scanner.research_telegram_eligible(item))
            self.assertFalse(scanner.telegram_eligible(item))

    def test_default_silent(self):
        with patch.dict("os.environ", {"ORACLE_RESEARCH_ALERTS": ""}), \
             patch.object(scanner, "decision_summary", return_value=("WAIT AND VERIFY", "review")):
            self.assertFalse(scanner.research_telegram_eligible(self.candidate()))

    def test_discard_never_notified(self):
        with patch.dict("os.environ", {"ORACLE_RESEARCH_ALERTS": "true"}), \
             patch.object(scanner, "decision_summary", return_value=("DISCARD", "risk")):
            self.assertFalse(scanner.research_telegram_eligible(self.candidate()))

    def test_missing_identity_or_market_silent(self):
        with patch.dict("os.environ", {"ORACLE_RESEARCH_ALERTS": "true"}), \
             patch.object(scanner, "decision_summary", return_value=("WAIT AND VERIFY", "review")):
            item = self.candidate()
            item["token_identity_status"] = "UNVERIFIED"
            self.assertFalse(scanner.research_telegram_eligible(item))
            item = self.candidate()
            item["liquidity"] = None
            self.assertFalse(scanner.research_telegram_eligible(item))

    def test_high_concern_silent(self):
        with patch.dict("os.environ", {"ORACLE_RESEARCH_ALERTS": "true"}), \
             patch.object(scanner, "decision_summary", return_value=("WAIT AND VERIFY", "review")):
            item = self.candidate()
            item["risk_category"] = "AVOID / HIGH CONCERN"
            self.assertFalse(scanner.research_telegram_eligible(item))


if __name__ == "__main__":
    unittest.main()
