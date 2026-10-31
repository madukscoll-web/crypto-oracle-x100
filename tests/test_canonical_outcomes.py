import copy
import unittest
from test_opportunity_alerts import candidate, breakout, NOW
from canonical_outcomes import assess, OUTCOMES

class CanonicalTests(unittest.TestCase):
    def test_high_score_and_candle_entry_remain_research_with_critical_gaps(self):
        for row in (candidate(), breakout(candidate())):
            result = assess(row, now=NOW)
            self.assertEqual(result['outcome'], 'RESEARCH WATCH')
            self.assertFalse(result['buy_authorized'])
            self.assertTrue(result['critical_gaps'])
    def test_reject_and_absence_remain_distinct(self):
        row = candidate(); row['verification']['sellability'] = {'status':'FAIL','reason':'Honeypot'}
        self.assertEqual(assess(row, now=NOW)['outcome'], 'REJECT')
        self.assertEqual(assess({}, now=NOW)['outcome'], 'INSUFFICIENT EVIDENCE')
    def test_forged_decisions_and_verified_flags_cannot_authorize(self):
        row = candidate()
        row.update(outcome='VERIFIED BUY', buy_authorized=True, eligible_for_buy=True,
                   sellability_verified=True, tokenomics_verified=True)
        self.assertNotEqual(assess(row, now=NOW)['outcome'], 'VERIFIED BUY')
        self.assertEqual(len(OUTCOMES), 5)
