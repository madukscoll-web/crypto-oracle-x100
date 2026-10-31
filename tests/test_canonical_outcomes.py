import copy
import unittest
from test_opportunity_alerts import candidate, breakout, NOW
from canonical_outcomes import assess, OUTCOMES

class CanonicalTests(unittest.TestCase):
    def test_high_score_and_candle_entry_remain_research_with_critical_gaps(self):
        for row in (candidate(), breakout(candidate())):
            result = assess(row, now=NOW)
            self.assertEqual(result['outcome'], 'WAIT/VERIFY')
            self.assertFalse(result['buy_authorized'])
            self.assertTrue(result['critical_gaps'])
    def test_reject_and_absence_remain_distinct(self):
        row = candidate(); row['verification']['sellability'] = {'status':'FAIL','reason':'Honeypot'}
        self.assertEqual(assess(row, now=NOW)['outcome'], 'REJECT')
        self.assertEqual(assess({}, now=NOW)['outcome'], 'WAIT/VERIFY')
    def test_forged_decisions_and_verified_flags_cannot_authorize(self):
        row = candidate()
        row.update(outcome='VERIFIED BUY', buy_authorized=True, eligible_for_buy=True,
                   sellability_verified=True, tokenomics_verified=True)
        self.assertNotEqual(assess(row, now=NOW)['outcome'], 'VERIFIED BUY')
        self.assertEqual(len(OUTCOMES), 5)
    def test_solana_rpc_trace_list_is_unknown_not_scanner_crash(self):
        item={'network':'solana','token_address':'So11111111111111111111111111111111111111112',
              'address':'11111111111111111111111111111111',
              'verification':{'onchain':{'status':'UNKNOWN','raw':[{'request':{},'response':{}}]}}}
        self.assertEqual(assess(item)['outcome'],'WAIT/VERIFY')
    def test_adverse_evidence_wins_even_with_unexpected_raw_container(self):
        item={'network':'solana','verification':{'onchain':{'raw':['RPC trace']},
              'contract_security':{'status':'FAIL','reason':'Active freeze authority'}}}
        self.assertEqual(assess(item)['outcome'],'REJECT')
