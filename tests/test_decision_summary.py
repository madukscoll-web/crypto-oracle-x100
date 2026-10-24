"""Decision footer tests, entirely offline."""
import unittest
import datetime as dt
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

    def test_assertions_and_synthetic_quote_never_authorize_buy(self):
        item = {
            "risk_category": "RESEARCH CANDIDATE — LIMITED CHECKS",
            "token_identity_status": "Base token from GeckoTerminal pool relationship",
            "sellability_verified": True,
            "liquidity_lock_verified": True,
            "holder_distribution_verified": True,
            "tokenomics_verified": True,
            "entry_risk_reviewed": True,
            "executable_quote_verified": True,
            "slippage_verified": True,
            "base_token_price_usd": 0.01,
            "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "network": "base", "token_address": "0xabc", "address": "0xpool",
            "execution_evidence": {"network": "base", "token_address": "0xabc",
                "pool_address": "0xpool", "provider": "fixture", "quote_id": "test",
                "verified": True, "provider_authenticated": True, "direction": "BUY",
                "amount_in": 100, "amount_out": 1000, "slippage_percent": 0.5,
                "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()},
            "score": 82, "liquidity": 300000, "volume": 500000,
            "buy_share": 0.58,
        }
        action, _ = decision_summary(item)
        self.assertEqual(action, "WAIT AND VERIFY")
        for key in ("sellability_verified", "liquidity_lock_verified",
                    "holder_distribution_verified", "tokenomics_verified",
                    "entry_risk_reviewed", "executable_quote_verified",
                    "slippage_verified", "base_token_price_usd", "observed_at",
                    "execution_evidence"):
            missing = dict(item)
            missing.pop(key)
            self.assertEqual(decision_summary(missing)[0], "WAIT AND VERIFY")

    def test_quote_for_wrong_pool_is_not_buy(self):
        from crypto_oracle_scanner import validate_execution_evidence
        evidence = {"network": "base", "token_address": "0xabc",
                    "pool_address": "0xother", "provider": "fixture",
                    "quote_id": "test", "verified": True,
                    "provider_authenticated": True, "direction": "BUY",
                    "amount_in": 100, "amount_out": 1000,
                    "slippage_percent": 0.5,
                    "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        self.assertFalse(validate_execution_evidence({"network": "base",
            "token_address": "0xabc", "address": "0xpool",
            "execution_evidence": evidence}))

    def test_manipulation_flag_blocks_buy(self):
        from crypto_oracle_scanner import decision_summary
        import datetime as dt
        item = {
            "risk_category": "RESEARCH CANDIDATE — LIMITED CHECKS",
            "token_identity_status": "Base token from GeckoTerminal pool relationship",
            "sellability_verified": True, "liquidity_lock_verified": True,
            "holder_distribution_verified": True, "tokenomics_verified": True,
            "entry_risk_reviewed": True, "executable_quote_verified": True,
            "slippage_verified": True, "network": "base",
            "token_address": "0xabc", "address": "0xpool",
            "base_token_price_usd": 0.01,
            "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "execution_evidence": {"network": "base", "token_address": "0xabc",
                "pool_address": "0xpool", "provider": "fixture", "quote_id": "test",
                "verified": True, "provider_authenticated": True,
                "direction": "BUY", "amount_in": 100, "amount_out": 1000,
                "slippage_percent": 0.5,
                "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()},
            "score": 90, "liquidity": 400000, "volume": 600000,
            "buy_share": 0.55, "flags": ["Elevated volume/liquidity ratio: investigate wash trading"],
        }
        self.assertEqual(decision_summary(item)[0], "WAIT AND VERIFY")

    def test_high_activity_alone_is_not_buy(self):
        action, _ = decision_summary({
            "risk_category": "RESEARCH CANDIDATE — LIMITED CHECKS",
            "token_identity_status": "Base token from GeckoTerminal pool relationship",
            "score": 100, "liquidity": 1000000, "volume": 3000000,
            "buy_share": 0.55,
        })
        self.assertEqual(action, "WAIT AND VERIFY")

    def test_limited_checks_do_not_generate_buy(self):
        action, reason = decision_summary({
            "risk_category": "RESEARCH CANDIDATE — LIMITED CHECKS",
            "token_identity_status": "Base token from GeckoTerminal pool relationship",
        })
        self.assertEqual(action, "WAIT AND VERIFY")
        self.assertIn("not a contract audit", reason)


if __name__ == "__main__":
    unittest.main()
