import datetime as dt
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as oracle


def sample(**updates):
    item = {
        "key": "base:0xpool", "network": "base", "address": "0xpool",
        "token_address": "0xtoken", "score": 80, "liquidity": 300000,
        "volume": 400000, "buy_share": 0.55, "flags": [],
        "change_h1": 6, "change_h24": 18, "trades": 180,
        "risk_category": "RESEARCH CANDIDATE — LIMITED CHECKS",
        "token_identity_status": "Base token from GeckoTerminal pool relationship",
        "base_token_price_usd": 0.05,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    item.update(updates)
    return item


class ScannerTests(unittest.TestCase):
    def test_market_setup_priority_is_not_buy(self):
        item = sample()
        self.assertEqual(oracle.setup_assessment(item)[0], "PRIORITY VERIFY")
        self.assertEqual(oracle.decision_summary(item)[0], "WAIT AND VERIFY")

    def test_critical_risk_rejected(self):
        self.assertEqual(oracle.setup_assessment(sample(risk_category="AVOID / HIGH CONCERN"))[0], "REJECT")

    def test_invalid_price_cannot_qualify(self):
        self.assertNotEqual(oracle.setup_assessment(sample(base_token_price_usd=0))[0], "PRIORITY VERIFY")

    def test_pump_is_not_priority(self):
        item = sample(change_h1=48, change_h24=80)
        self.assertEqual(oracle.setup_assessment(item)[0], "WAIT")

    def test_stale_price_is_not_priority(self):
        item = sample(observed_at="2025-01-01T00:00:00+00:00")
        self.assertNotEqual(oracle.setup_assessment(item)[0], "PRIORITY VERIFY")

    def test_momentum_watch(self):
        item = sample(change_h1=6, change_h24=18, trades=180, buy_share=0.58)
        self.assertEqual(oracle.entry_setup(item)[0], "MOMENTUM WATCH")
        self.assertEqual(oracle.decision_summary(item)[0], "WAIT AND VERIFY")

    def test_pullback_watch(self):
        item = sample(change_h1=-2, change_h24=8, trades=180, buy_share=0.55)
        self.assertEqual(oracle.entry_setup(item)[0], "PULLBACK WATCH")

    def test_overextended_rejected_as_entry(self):
        item = sample(change_h1=45, change_h24=90, trades=180)
        self.assertEqual(oracle.entry_setup(item)[0], "OVEREXTENDED")

    def test_missing_change_data_is_not_a_setup(self):
        item = sample(change_h1=None, change_h24=None, trades=180)
        self.assertEqual(oracle.entry_setup(item)[0], "INSUFFICIENT DATA")

    def test_configurable_risk_plan(self):
        with patch.dict(oracle.os.environ, {"ORACLE_BUDGET_NGN": "100000",
                                           "ORACLE_RISK_FRACTION": "0.01",
                                           "ORACLE_MAX_ALLOCATION_FRACTION": "0.05"}):
            result = oracle.investment_plan(sample(), "BUY CANDIDATE — REVIEW ENTRY")
        self.assertIn("NGN 5,000", result)
        self.assertIn("NGN 1,000", result)

    def test_transition_only_when_priority_improves(self):
        state = {}
        item = sample(score=62)
        self.assertIsNone(oracle.watchlist_transition(item, state))
        item["score"] = 80
        self.assertEqual(oracle.watchlist_transition(item, state), "UPGRADED TO PRIORITY")
        self.assertIsNone(oracle.watchlist_transition(item, state))


if __name__ == "__main__":
    unittest.main()
