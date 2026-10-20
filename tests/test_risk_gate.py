"""Offline tests for security triage; no network calls or credentials."""
import unittest
from crypto_oracle_scanner import risk_gate, risk_gate_unavailable


class RiskGateTests(unittest.TestCase):
    def test_honeypot(self):
        self.assertEqual(risk_gate({"is_honeypot": "1"})[0], "AVOID / HIGH CONCERN")

    def test_balance_change(self):
        self.assertEqual(risk_gate({"owner_change_balance": "1"})[0], "AVOID / HIGH CONCERN")

    def test_hidden_owner(self):
        self.assertEqual(risk_gate({"hidden_owner": "1"})[0], "AVOID / HIGH CONCERN")

    def test_blacklist(self):
        self.assertEqual(risk_gate({"is_blacklisted": "1"})[0], "AVOID / HIGH CONCERN")

    def test_mintable(self):
        self.assertEqual(risk_gate({"is_mintable": "1"})[0], "WAIT / VERIFY")

    def test_closed_source(self):
        self.assertEqual(risk_gate({"is_open_source": "0"})[0], "WAIT / VERIFY")

    def test_unknown_security(self):
        self.assertEqual(risk_gate({})[0], "WAIT / VERIFY")

    def test_unavailable_security(self):
        self.assertEqual(risk_gate_unavailable("API unavailable")[0], "WAIT / VERIFY")

    def test_partial_negative_is_not_audit(self):
        label, reasons = risk_gate({"is_honeypot": "0"})
        self.assertEqual(label, "RESEARCH CANDIDATE — LIMITED CHECKS")
        self.assertIn("not proof of safety", reasons[0])

    def test_holder_concentration_descriptive(self):
        label, reasons = risk_gate({"is_honeypot": "0"}, 0.666, 10)
        self.assertEqual(label, "WAIT / VERIFY")
        self.assertTrue(any("LP/exclusions unknown" in x for x in reasons))


if __name__ == "__main__":
    unittest.main()
