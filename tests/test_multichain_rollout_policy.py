import unittest
from multichain_rollout_policy import PLANS, plan, eligible_for_buy

class RolloutPolicyTests(unittest.TestCase):
    def test_priorities_unique(self):
        self.assertEqual([x.priority for x in PLANS], list(range(1, len(PLANS)+1)))
        self.assertEqual(PLANS[0].network, "solana")
    def test_solana_has_specific_checks(self):
        self.assertIn("mint_and_freeze_authorities", plan("solana").required_checks)
        self.assertIn("token_2022_extensions", plan("solana").required_checks)
    def test_empty_evidence_fails_closed(self):
        for item in PLANS:
            result = eligible_for_buy(item.network, {})
            self.assertFalse(result["buy_authorized"])
            self.assertTrue(result["missing"])
    def test_planned_chain_never_activates(self):
        item = plan("sui")
        all_verified = {name: {"status": "VERIFIED"} for name in item.required_checks}
        result = eligible_for_buy("sui", all_verified)
        self.assertIn("production_chain_adapter", result["missing"])
        self.assertFalse(result["buy_authorized"])
    def test_unknown_chain(self):
        self.assertEqual(eligible_for_buy("unknown", {})["status"], "UNSUPPORTED")

if __name__ == "__main__":
    unittest.main()
