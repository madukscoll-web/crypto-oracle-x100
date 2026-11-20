import unittest

import identity_sources
import investment_gates


class IdentitySourceTests(unittest.TestCase):
    def test_only_exact_provider_relationship_statuses_pass(self):
        ok = ["Base token from GeckoTerminal pool relationship", "Base token from DexScreener pool relationship"]
        for status in ok:
            self.assertTrue(identity_sources.identity_verified({"token_identity_status": status}))
        for status in (None, "", "UNVERIFIED", "UNVERIFIED (returned pool identity mismatch)",
                       "Base token from Random pool relationship", "base token from dexscreener pool relationship"):
            self.assertFalse(identity_sources.identity_verified({"token_identity_status": status}), status)
        self.assertFalse(identity_sources.identity_verified(None))

    def test_no_gate_still_hardcodes_a_single_provider(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("evidence_audit.py", "investment_gates.py", "crypto_oracle_scanner.py", "opportunity_alerts.py"):
            text = (root / name).read_text()
            self.assertNotIn("!= \"Base token from GeckoTerminal pool relationship\"", text)
            self.assertNotIn("!='Base token from GeckoTerminal pool relationship'", text)
            self.assertIn("identity_sources.identity_verified", text)

    def test_dexscreener_identity_alone_does_not_clear_other_blockers(self):
        item = {"token_identity_status": "Base token from DexScreener pool relationship",
                "token_address": "0xBase000000000000000000000000000000000001", "network": "base"}
        result = investment_gates.assess(item)
        self.assertNotIn("Exact base-token identity unverified", result["blockers"])
        self.assertIn("Provider security assessment unavailable", result["blockers"])
        self.assertFalse(result["buy_eligible"])
        spoof = dict(item, token_identity_status="Base token from Random pool relationship")
        self.assertIn("Exact base-token identity unverified", investment_gates.assess(spoof)["blockers"])

if __name__ == "__main__":
    unittest.main()
