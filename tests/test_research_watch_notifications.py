"""Research WATCH messages are distinct from verified BUY alerts."""
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner

class ResearchWatchTests(unittest.TestCase):
    def item(self):
        return dict(risk_category="WAIT / VERIFY", network="bsc",
                    token_address="0x"+"a"*40, address="0x"+"b"*40,
                    liquidity=300000, volume=400000, trades=100,
                    buy_share=0.6, change_h1=2, change_h24=8,
                    score=80, flags=[], token_symbol="TEST", risk_reasons=["Unlocks unknown"])
    def test_high_risk_excluded(self):
        x=self.item();x["risk_category"]="AVOID / HIGH CONCERN"
        self.assertFalse(scanner.research_alert_eligible(x))
    def test_incomplete_market_excluded(self):
        x=self.item();x["liquidity"]=None
        self.assertFalse(scanner.research_alert_eligible(x))
    def test_no_buy_claim(self):
        x=self.item()
        with patch.object(scanner,"decision_summary",return_value=("WAIT / VERIFY","Needs evidence")), patch.object(scanner,"setup_assessment",return_value=("PRIORITY VERIFY","Strong observed activity")), patch.object(scanner,"price_evidence",return_value=(True,"ok")):
            self.assertTrue(scanner.research_alert_eligible(x))
            message=scanner.research_alert_text(x)
            self.assertIn("NOT APPROVED FOR PURCHASE",message)
            self.assertIn(x["token_address"],message)

    def test_wait_with_credible_market_data(self):
        x=self.item();x["score"]=65;x["liquidity"]=150000;x["volume"]=120000
        with patch.object(scanner,"decision_summary",return_value=("WAIT AND VERIFY","Incomplete evidence")), patch.object(scanner,"setup_assessment",return_value=("WAIT","No confirmed reversal")), patch.object(scanner,"price_evidence",return_value=(True,"ok")):
            self.assertTrue(scanner.research_alert_eligible(x))
            self.assertIn("WAIT",scanner.research_alert_text(x))
    def test_wait_without_credible_activity_is_silent(self):
        x=self.item();x["score"]=20
        with patch.object(scanner,"decision_summary",return_value=("WAIT AND VERIFY","Incomplete evidence")), patch.object(scanner,"setup_assessment",return_value=("WAIT","Weak market activity")):
            self.assertFalse(scanner.research_alert_eligible(x))
    def test_tokenized_stock_reference_is_silent(self):
        x=self.item()
        x["verification"]={"tokenized_stock_reference":{"status":"LIMITED","reason":"stock-backed reference"}}
        with patch.object(scanner,"decision_summary",return_value=("WAIT AND VERIFY","Pending")), patch.object(scanner,"setup_assessment",return_value=("PRIORITY VERIFY","Activity")):
            self.assertFalse(scanner.research_alert_eligible(x))

    def test_explicit_excluded_asset_categories_are_silent(self):
        for category in ("TOKENIZED_STOCK","TOKENIZED_SECURITY","STABLECOIN","WRAPPED_ASSET","PEGGED_ASSET"):
            with self.subTest(category=category):
                x=self.item()
                x["asset_category"]=category
                with patch.object(scanner,"decision_summary",return_value=("WAIT AND VERIFY","Pending")), patch.object(scanner,"setup_assessment",return_value=("PRIORITY VERIFY","Activity")):
                    self.assertFalse(scanner.research_alert_eligible(x))

    def test_unverified_identity_is_silent(self):
        x=self.item();x["token_identity_status"]="UNVERIFIED (mismatch)"
        with patch.object(scanner,"decision_summary",return_value=("WAIT AND VERIFY","Identity unknown")), patch.object(scanner,"setup_assessment",return_value=("PRIORITY VERIFY","Activity")):
            self.assertFalse(scanner.research_alert_eligible(x))
