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
