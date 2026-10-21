import unittest
import evidence_audit


class EvidenceAuditTests(unittest.TestCase):
    def test_missing_evidence_never_trade_ready(self):
        result = evidence_audit.audit({"liquidity": 300000, "volume": 400000})
        self.assertFalse(result["trade_ready"])
        self.assertIn("sellability", result["unknown"])

    def test_bare_boolean_claims_are_not_verification(self):
        result = evidence_audit.audit({
            "sellability_verified": True,
            "liquidity_lock_verified": True,
            "holder_distribution_verified": True,
            "tokenomics_verified": True,
            "executable_quote_verified": True,
            "slippage_verified": True,
        })
        for name in ("sellability", "liquidity_lock", "holder_distribution",
                     "tokenomics_unlocks", "execution_quote"):
            self.assertEqual(result["checks"][name], "UNKNOWN")
        self.assertFalse(result["trade_ready"])

    def test_high_concern_rejected(self):
        result = evidence_audit.audit({
            "risk_category": "AVOID / HIGH CONCERN",
            "liquidity": 300000, "volume": 400000
        })
        self.assertEqual(result["research_status"], "REJECT")
        self.assertEqual(result["checks"]["provider_risk"], "FAIL")

    def test_market_activity_cannot_substitute_for_security(self):
        result = evidence_audit.audit({
            "liquidity": 900000, "volume": 1000000,
            "entry_pattern": "MOMENTUM WATCH",
        })
        self.assertEqual(result["checks"]["market_depth"], "PASS")
        self.assertFalse(result["trade_ready"])


if __name__ == "__main__":
    unittest.main()
