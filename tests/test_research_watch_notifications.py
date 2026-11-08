"""Research WATCH messages are distinct from verified BUY alerts."""
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner

class ResearchWatchTests(unittest.TestCase):
    def test_bound_preliminary_research_is_independent_of_buy_and_sent_with_label(self):
        from tests.test_opportunity_alerts import candidate, NOW
        import datetime as dt
        import opportunity_alerts
        x=candidate();x.update(token_symbol='TEST',source='Fixture discovery',risk_reasons=['Advanced evidence incomplete'])
        self.assertTrue(scanner.research_alert_eligible(x,now=NOW))
        self.assertFalse(scanner.telegram_eligible(x))
        real_classify=opportunity_alerts.classify
        with patch.object(opportunity_alerts,'classify',side_effect=lambda item,now=None:real_classify(item,now=NOW)), \
             patch.object(scanner,'decision_summary',return_value=('WAIT AND VERIFY','Advanced evidence incomplete')), \
             patch.object(scanner,'setup_assessment',return_value=('WATCH','Preliminary activity only')), \
             patch('telegram_notify._send_message',return_value=True) as send:
            self.assertTrue(scanner.send_discovery_research(x))
            text=send.call_args.args[0]
            self.assertEqual(text.splitlines()[0],'NEW TOKEN DISCOVERY')
            self.assertIn('NOT APPROVED FOR PURCHASE',text)
            self.assertIn('Fixture discovery',text)
            self.assertIn(x['token_address'],text)
            self.assertNotIn('BUY CANDIDATE',text)
            x['verification']['contract_security']['raw']['result'][x['token_address']]['cannot_sell_all']='1'
            with self.assertRaises(ValueError):scanner.send_discovery_research(x)
            self.assertEqual(send.call_count,1)

    def test_preliminary_research_stale_or_wrong_contract_is_silent(self):
        from tests.test_opportunity_alerts import candidate, NOW
        for mutation in ('stale','contract','uncorroborated','prior_adverse','category'):
            x=candidate()
            if mutation=='stale':x['observed_at']='2020-01-01T00:00:00+00:00'
            elif mutation=='contract':x['token_address']='0x'+'3'*40
            elif mutation=='uncorroborated':x['market_corroboration']['status']='UNKNOWN'
            elif mutation=='prior_adverse':x['persistent_adverse_reasons']=['Known sellability concern']
            else:x['asset_category']='STABLECOIN'
            self.assertFalse(scanner.research_alert_eligible(x,now=NOW),mutation)

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
            self.assertFalse(scanner.research_alert_eligible(x))
            message=scanner.research_alert_text(x)
            self.assertIn("NOT APPROVED FOR PURCHASE",message)
            self.assertIn(x["token_address"],message)

    def test_wait_with_credible_market_data(self):
        x=self.item();x["score"]=65;x["liquidity"]=150000;x["volume"]=120000
        with patch.object(scanner,"decision_summary",return_value=("WAIT AND VERIFY","Incomplete evidence")), patch.object(scanner,"setup_assessment",return_value=("WAIT","No confirmed reversal")), patch.object(scanner,"price_evidence",return_value=(True,"ok")):
            self.assertFalse(scanner.research_alert_eligible(x))
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

