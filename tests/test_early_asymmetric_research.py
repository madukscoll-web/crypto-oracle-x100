import unittest
from datetime import datetime, timezone
from early_asymmetric_research import evaluate

class EarlyAsymmetricTests(unittest.TestCase):
    def base(self):
        return dict(chain="base", contract="0x123", source_url="https://example.org/evidence",
            observed_at=datetime.now(timezone.utc).isoformat(), market_cap_usd=8_000_000,
            fdv_usd=16_000_000, volume_24h_usd=200_000, liquidity_usd=200_000,
            security_verified=True, supply_verified=True, identity_verified=True,
            scores=dict(fundamentals=15, tokenomics=10, liquidity_security=12,
                        adoption_catalysts=13, early_momentum=9))
    def test_research_only_even_fully_populated(self):
        r=evaluate(self.base())
        self.assertTrue(r["eligible_for_rank"])
        self.assertFalse(r["buy_authorized"])
        self.assertEqual(r["classification"], "RESEARCH WATCH")
        self.assertEqual(r["score_out_of_100"], 59)
        self.assertEqual(r["scenario_market_caps_usd"]["100x"], 800_000_000)
        self.assertIsNone(r["probability_of_100x"])
    def test_missing_security_fails_closed(self):
        d=self.base(); d["security_verified"]=False
        self.assertIn("security_unverified", evaluate(d)["blockers"])
    def test_high_dilution_fails_closed(self):
        d=self.base(); d["fdv_usd"]=100_000_000
        self.assertIn("high_dilution", evaluate(d)["blockers"])
    def test_forged_score_fails_closed(self):
        d=self.base(); d["scores"]["fundamentals"]=100
        self.assertFalse(evaluate(d)["eligible_for_rank"])
    def test_bad_timestamp_fails_closed(self):
        d=self.base(); d["observed_at"]="yesterday"
        self.assertFalse(evaluate(d)["eligible_for_rank"])
    def test_low_liquidity_fails_closed(self):
        d=self.base(); d["liquidity_usd"]=100
        self.assertIn("thin_liquidity", evaluate(d)["blockers"])

if __name__ == "__main__":
    unittest.main()
