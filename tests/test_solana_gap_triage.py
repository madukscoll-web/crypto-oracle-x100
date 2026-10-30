import unittest
from solana_gap_triage import triage

class SolanaGapTriageTests(unittest.TestCase):
    def test_empty_is_not_buy(self):
        result = triage({})
        self.assertFalse(result["buy_authorized"])
        self.assertEqual(result["status"], "RESEARCH_ONLY")
        self.assertEqual(result["gates"]["holders"]["status"], "NOT_CHECKED")
    def test_active_mint_authority_rejects(self):
        result = triage({"onchain": {"status": "LIMITED", "checks": {
            "mint_authority_revoked": {"status": "FAILED"}}}})
        self.assertEqual(result["status"], "REJECT")
        self.assertFalse(result["orders_allowed"])
    def test_token_2022_unsupported(self):
        result = triage({"onchain": {"status": "UNSUPPORTED",
                         "reason": "Token-2022 requires reviewed parser"}})
        self.assertTrue(any("Token-2022" in x for x in result["blockers"]))
    def test_no_false_holder_verification(self):
        result = triage({"holders": {"status": "UNKNOWN",
                         "reason": "Largest accounts are not beneficial owners"}})
        self.assertEqual(result["gates"]["holders"]["status"], "UNKNOWN")
        self.assertFalse(result["buy_authorized"])

if __name__ == "__main__":
    unittest.main()
