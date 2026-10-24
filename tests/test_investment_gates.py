"""Deterministic evidence-gate regression tests."""
import unittest
from unittest.mock import patch
import investment_gates

class GateTests(unittest.TestCase):
    def item(self, **kw):
        result = dict(score=100, network="base", address="pool", token_address="0xabc",
            token_identity_status="Base token from GeckoTerminal pool relationship",
            risk_category="WAIT / VERIFY", security_source="GoPlus token_security API",
            source="GeckoTerminal public API", observed_at="2026-10-24T04:00:00+00:00",
            liquidity=2462359, volume=11937399)
        result.update(kw)
        return result

    def test_axis_activity_never_becomes_buy(self):
        r = investment_gates.assess(self.item())
        self.assertFalse(r["buy_eligible"])
        self.assertIn("Circulating/maximum supply unverified", r["blockers"])
        self.assertEqual(r["activity"]["score"], 100)

    def test_critical_security(self):
        r = investment_gates.assess(self.item(risk_category="AVOID / HIGH CONCERN"))
        self.assertEqual(r["security"], "HIGH CONCERN")

    def test_supply_conflict(self):
        r = investment_gates.assess(self.item(circulating_supply=200, max_supply=100))
        self.assertIn("Conflicting supply: circulating exceeds maximum", r["blockers"])

    def test_dilution(self):
        r = investment_gates.assess(self.item(market_cap_usd=1_000_000, fdv_usd=10_000_000))
        self.assertTrue(any("FDV/circulating" in w for w in r["warnings"]))

    def test_concentration_unverified_without_exclusions(self):
        r = investment_gates.assess(self.item(adjusted_top10_fraction=.9))
        self.assertTrue(any("Top-holder" in b for b in r["blockers"]))

    def test_bad_quote_and_thin_depth(self):
        r = investment_gates.assess(self.item(execution_evidence={"spread_percent": -1, "depth_usd": 20}))
        self.assertTrue(any("crossed" in b for b in r["blockers"]))
        self.assertTrue(any("Thin executable" in w for w in r["warnings"]))

    def test_invalid_unlock(self):
        r = investment_gates.assess(self.item(next_unlock_utc="not-a-date", unlock_source_verified=True))
        self.assertIn("Invalid unlock timestamp", r["blockers"])

    def test_provider_flags_not_independent(self):
        r = investment_gates.assess(self.item(sellability_verified=True, liquidity_lock_verified=True,
                                               tokenomics_verified=True, holder_distribution_verified=True))
        self.assertFalse(r["buy_eligible"])

    def test_missing_identity(self):
        r = investment_gates.assess(self.item(token_identity_status="UNVERIFIED"))
        self.assertIn("Exact base-token identity unverified", r["blockers"])

    def test_vinu_unknown_supply(self):
        r = investment_gates.assess(self.item(network="bsc", token_address="0xfebe8c1ed424dbf688551d4e2267e7a53698f0aa"))
        self.assertFalse(r["buy_eligible"])

    def test_cross_pool_quote_rejected(self):
        r = investment_gates.assess(self.item(execution_evidence={
            "network": "base", "pool_address": "other-pool", "token_address": "0xabc",
            "observed_at": "2026-10-24T04:00:00+00:00", "source": "test",
            "source_url": "https://example.org", "spread_percent": .1, "depth_usd": 5000}))
        self.assertTrue(any("pool_address mismatched" in b for b in r["blockers"]))

    def test_missing_quote_provenance_rejected(self):
        r = investment_gates.assess(self.item(execution_evidence={
            "network": "base", "pool_address": "pool", "token_address": "0xabc",
            "observed_at": "invalid", "spread_percent": .1, "depth_usd": 5000}))
        self.assertTrue(any("source provenance" in b for b in r["blockers"]))

if __name__ == "__main__":
    unittest.main()

