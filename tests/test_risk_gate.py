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

    def test_cannot_sell_all_is_discard(self):
        self.assertEqual(risk_gate({"cannot_sell_all": "1"})[0], "AVOID / HIGH CONCERN")

    def test_unknown_sellability_blocks_research_label(self):
        info = {"is_honeypot": "0", "owner_change_balance": "0",
                "hidden_owner": "0", "is_blacklisted": "0",
                "is_open_source": "1", "is_mintable": "0",
                "trading_cooldown": "0"}
        self.assertEqual(risk_gate(info)[0], "WAIT / VERIFY")

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
        self.assertEqual(label, "WAIT / VERIFY")
        self.assertIn("Missing or uninterpretable", reasons[0])

    def test_complete_core_fields_can_be_limited_research(self):
        info = {"is_honeypot": "0", "owner_change_balance": "0",
                "hidden_owner": "0", "is_blacklisted": "0",
                "cannot_sell_all": "0",
                "is_open_source": "1", "is_mintable": "0",
                "trading_cooldown": "0"}
        label, reasons = risk_gate(info)
        self.assertEqual(label, "RESEARCH CANDIDATE — LIMITED CHECKS")
        self.assertIn("not proof of safety", reasons[0])

    def test_holder_concentration_descriptive(self):
        label, reasons = risk_gate({"is_honeypot": "0"}, 0.666, 10)
        self.assertEqual(label, "WAIT / VERIFY")
        self.assertTrue(any("LP/exclusions unknown" in x for x in reasons))


if __name__ == "__main__":
    unittest.main()



class ProviderBooleanTests(unittest.TestCase):
    def test_explicit_boolean_honeypot_is_adverse(self):
        self.assertEqual(risk_gate({'is_honeypot': True})[0], 'AVOID / HIGH CONCERN')
        self.assertEqual(risk_gate({'is_open_source': False})[0], 'WAIT / VERIFY')
