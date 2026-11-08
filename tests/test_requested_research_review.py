import unittest
from unittest.mock import patch
import requested_research_review as r
from test_technical_watch import fixture, NOW


class RequestedReviewTests(unittest.TestCase):
    def test_current_setup_replays_same_safety_rules_and_labels_requested_refresh(self):
        report,fetch=fixture()
        notice,result=r.review(report,fetch,negatives=set(),now=lambda:NOW)
        self.assertEqual(result['status'],'QUALIFYING_TECHNICAL_REASSESSMENT')
        self.assertIn('BULLISH REVERSAL WATCH',str(notice).splitlines()[0])
        self.assertIn('OWNER-REQUESTED CURRENT REASSESSMENT',notice)
        self.assertIn('Invalidation reference:',notice)
        self.assertFalse(result['new_automated_signal'])
        self.assertFalse(result['buy_authorized'])

    def test_adverse_finding_is_not_bypassed_for_demonstration(self):
        report,fetch=fixture(adverse=True)
        notice,result=r.review(report,fetch,negatives=set(),now=lambda:NOW)
        self.assertIsNone(notice)
        self.assertIn('Adverse contract capability/sellability finding',result['rejection_reasons'])

    def test_stale_book_is_rejected_and_no_opportunity_is_invented(self):
        report,original=fixture()
        def fetch(url):
            data=original(url)
            if '/spot/order_book?' in url:data.update(current=int((NOW-60)*1000),update=int((NOW-60)*1000))
            return data
        notice,result=r.review(report,fetch,negatives=set(),now=lambda:NOW)
        self.assertIsNone(notice)
        self.assertEqual(result['status'],'NO_SETUP_PASSED_BOUNDED_REVIEW')

    def test_receipt_must_match_configured_destination(self):
        report,fetch=fixture()
        notice,result=r.review(report,fetch,negatives=set(),now=lambda:NOW)
        def transport(token,method,data):
            if method=='getMe':return {'ok':True,'result':{'is_bot':True}}
            if method=='getChat':return {'ok':True,'result':{'id':123,'type':'private'}}
            return {'ok':True,'result':{'message_id':7,'chat':{'id':999}}}
        with self.assertRaises(ValueError):
            r.transmit(notice,result,{'TELEGRAM_BOT_TOKEN':'test','TELEGRAM_CHAT_ID':'123'},transport)
        self.assertFalse(result['delivery_confirmed'])

    def test_confirmed_requested_review_records_receipt_without_signal_cohort(self):
        report,fetch=fixture()
        notice,result=r.review(report,fetch,negatives=set(),now=lambda:NOW)
        def transport(token,method,data):
            if method=='getMe':return {'ok':True,'result':{'is_bot':True}}
            if method=='getChat':return {'ok':True,'result':{'id':123,'type':'private'}}
            return {'ok':True,'result':{'message_id':7,'chat':{'id':123}}}
        r.transmit(notice,result,{'TELEGRAM_BOT_TOKEN':'test','TELEGRAM_CHAT_ID':'123'},transport)
        self.assertTrue(result['delivery_confirmed'])
        self.assertEqual(result['telegram_message_id'],7)
        self.assertFalse(result['new_automated_signal'])
