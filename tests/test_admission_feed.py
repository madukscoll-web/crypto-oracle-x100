import unittest
from unittest.mock import patch
import admission_feed
import admission_preflight

class FeedTests(unittest.TestCase):
    def setUp(self):
        admission_feed._CACHE.clear()
        self.identity={'network':'eth','token':'0x'+'1'*40,'pool':'0x'+'2'*40}
        self.trust={'bundle_endpoint':'https://review.example/bundle','reviewers':{'one':{},'two':{}}}
    def test_intake_is_bound_and_cached_but_never_claims_verification(self):
        requests=[]
        def fetch(url):requests.append(url);return {'payload':{'fabricated':True}}
        result=admission_feed.collect(self.identity,self.trust,fetch,lambda:1)
        result['payload']['fabricated']=False
        self.assertTrue(admission_feed.collect(self.identity,self.trust,fetch,lambda:2)['payload']['fabricated'])
        self.assertEqual(len(requests),1)
        self.assertIn('network=eth',requests[0]);self.assertIn(self.identity['token'],requests[0])
    def test_unenrolled_insecure_credentialed_and_redirect_like_urls_block(self):
        for endpoint in ('http://review.example/bundle','https://user:password@review.example/bundle',
                         'https://review.example:8443/bundle','https://review.example/bundle?target=evil','https://review.example/bundle#fragment'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                admission_feed.collect(self.identity,dict(self.trust,bundle_endpoint=endpoint),lambda url:self.fail('Must not fetch'))
        with self.assertRaises(ValueError):admission_feed.collect(self.identity,dict(self.trust,reviewers={}))
    def test_outage_negative_cache_does_not_flood_provider(self):
        attempts=[]
        def fetch(url):attempts.append(url);raise OSError('Synthetic provider outage')
        for when in (1,2,6):
            with self.assertRaises(ValueError):admission_feed.collect(self.identity,self.trust,fetch,lambda:when)
        self.assertEqual(len(attempts),2)
    def test_readiness_does_not_expose_credential_values(self):
        report=admission_preflight.inspect({'ZEROX_API_KEY':'synthetic-secret-never-print'})
        self.assertNotIn('synthetic-secret-never-print',str(report))
        self.assertTrue(report['configured']['ZEROX_API_KEY'])
        self.assertFalse(report['delivery_verified']);self.assertFalse(report['orders_allowed'])
        self.assertEqual(report['status'],'BLOCKED')
    def test_malformed_trust_readiness_is_blocked_without_interrupting_scanner(self):
        for value in ([],None,{'reviewers':True}):
            with patch.object(admission_preflight,'load_trust',return_value=value):
                report=admission_preflight.inspect({})
                self.assertEqual(report['status'],'BLOCKED')
                self.assertIn('Trust registry missing or malformed',report['blockers'])

