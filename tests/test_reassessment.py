import copy
import unittest
from unittest.mock import patch
import reassess_candidates as review


class ReassessmentTests(unittest.TestCase):
    def test_saved_backlog_is_not_dropped_when_discovery_filters_change(self):
        pool={'id':'base_pool','attributes':{'address':'pool'},'relationships':{'base_token':{'data':{'id':'base_0x'+'1'*40}}}}
        old={'discovery':[{'network':'base','mode':'new_pools','raw':{'data':[pool]}}],
             'not_enriched_pool_keys':['base:pool'],'candidates':[{'key':'eth:old','decision':'WAIT AND VERIFY'}, {'key':'eth:bad','decision':'DISCARD'}]}
        snapshot=copy.deepcopy(old)
        with patch.object(review.scanner,'inspect',return_value=None):result=review.targets(old)
        self.assertEqual([x['key'] for x in result],['base:pool','eth:old'])
        self.assertTrue(result[0]['historical_discovery_qualified'])
        self.assertEqual(result[0]['review_cohort'],'previously_unassessed_qualified')
        self.assertEqual(old,snapshot)

    def test_unavailable_fresh_provider_cannot_erase_prior_failure(self):
        previous={'decision':'WAIT AND VERIFY','verification':{'sellability':{'status':'FAIL','reason':'Independent adverse evidence','observed_at':'2026-10-21T00:00:00+00:00'}}}
        item={'decision':'BUY NOW — VERIFIED SETUP','mandatory_blockers':[],'verification':{}}
        with patch.object(review.evidence_audit,'audit',return_value={'trade_ready':False}):review.preserve_adverse(item,previous)
        self.assertEqual(item['decision'],'WAIT AND VERIFY')
        self.assertEqual(item['unresolved_prior_adverse_evidence'][0]['evidence']['observed_at'],'2026-10-21T00:00:00+00:00')
        self.assertIn('Unresolved prior sellability',item['mandatory_blockers'][0])

    def test_position_count_is_distinct_from_owner_address_count(self):
        from live_candidate_scan import coverage
        rows=[{'status':'LIMITED','metrics':{'position_manager':'manager','token_id':str(i),'owner':'same-owner'}} for i in (1,2)]
        item={'network':'base','verification':{'nft_custody':{'raw':{'records':rows}}}}
        result=coverage([item,item])
        self.assertEqual(result['unique_nft_positions_with_owner_corroboration'],2)
        self.assertEqual(result['unique_nft_owner_addresses_corroborated'],1)

    def test_current_rejection_is_preserved_with_prior_conflict(self):
        item={'decision':'DISCARD','decision_reason':'Current honeypot','mandatory_blockers':[],'verification':{}}
        previous={'decision':'WAIT AND VERIFY','verification':{'supply_comparison':{'status':'CONFLICTING'}}}
        with patch.object(review.evidence_audit,'audit',return_value={'trade_ready':False}):review.preserve_adverse(item,previous)
        self.assertEqual(item['decision'],'DISCARD')
        self.assertEqual(item['decision_reason'],'Current honeypot')

if __name__=='__main__':unittest.main()
