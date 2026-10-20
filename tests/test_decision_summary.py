"""Decision footer tests, entirely offline."""
import unittest
from crypto_oracle_scanner import decision_summary


class DecisionSummaryTests(unittest.TestCase):
    def test_critical_flag_is_discard(self):
        action, reason = decision_summary({
            "risk_category": "AVOID / HIGH CONCERN",
            "risk_reasons": ["is_honeypot=1: Provider reports honeypot"],
        })
        self.assertEqual(action, "DISCARD")
        self.assertIn("honeypot", reason)

    def test_incomplete_security_is_wait(self):
        action, reason = decision_summary({
            "risk_category": "WAIT / VERIFY",
            "risk_reasons": ["Security provider unavailable"],
            "token_identity_status": "Base token from GeckoTerminal pool relationship",
        })
        self.assertEqual(action, "WAIT AND VERIFY")
        self.assertIn("Security provider unavailable", reason)

    def test_unverified_identity_is_wait(self):
        action, reason = decision_summary({
            "risk_category": "WAIT / VERIFY",
            "token_identity_status": "UNVERIFIED",
        })
        self.assertEqual(action, "WAIT AND VERIFY")
        self.assertIn("identity", reason.lower())

    def test_limited_checks_do_not_generate_buy(self):
        action, reason = decision_summary({
            "risk_category": "RESEARCH CANDIDATE — LIMITED CHECKS",
            "token_identity_status": "Base token from GeckoTerminal pool relationship",
        })
        self.assertEqual(action, "WAIT AND VERIFY")
        self.assertIn("not a contract audit", reason)


if __name__ == "__main__":
    unittest.main()
