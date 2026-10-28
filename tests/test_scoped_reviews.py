import copy
import datetime as dt
import unittest
import holder_bounds as h
import scoped_authority_review as s

NOW=dt.datetime.fromisoformat(s.REVIEW['reviewed_at']).timestamp()+60
A=lambda i:'0x'+format(i,'040x')

class ScopedReviewTests(unittest.TestCase):
    def source(self):return dict(status='LIMITED',observed_at=dt.datetime.fromtimestamp(NOW,dt.timezone.utc).isoformat(),metrics=dict(runtime_source_match=True,source_sha256=s.REVIEW['source_hashes'].copy(),runtime_sha256=s.REVIEW['runtime_hash'],proxy_resolution=dict(isProxy=False),compiler=dict(compilerVersion=s.REVIEW['compiler_version'])))
    def test_exact_code_review_is_scoped_and_never_trade_authority(self):
        r=s.assess(dict(network='eth',token_address=s.LINK),self.source(),NOW)
        self.assertEqual(r['status'],'SCOPED_TECHNICAL_REVIEW_MATCH');self.assertFalse(r['buy_authorized']);self.assertFalse(r['independent_audit_completed'])
    def test_changed_code_proxy_compiler_or_freshness_does_not_inherit_review(self):
        for change in ('code','extra_source','proxy','compiler','stale'):
            source=self.source()
            if change=='code':source['metrics']['runtime_sha256']='fake'
            if change=='extra_source':source['metrics']['source_sha256']['Extra.sol']='fake'
            if change=='proxy':source['metrics']['proxy_resolution']['isProxy']=True
            if change=='compiler':source['metrics']['compiler']['compilerVersion']='new'
            if change=='stale':source['observed_at']='2020-01-01T00:00:00+00:00'
            self.assertEqual(s.assess(dict(network='eth',token_address=s.LINK),source,NOW)['status'],'UNKNOWN')
    def test_wrong_chain_contract_or_expired_review_cannot_pass(self):
        self.assertEqual(s.assess(dict(network='bsc',token_address=s.LINK),self.source(),NOW)['status'],'UNKNOWN')
        self.assertEqual(s.assess(dict(network='eth',token_address=A(1)),self.source(),NOW)['status'],'UNKNOWN')
        self.assertEqual(s.assess(dict(network='eth',token_address=s.LINK),self.source(),NOW+8*86400)['status'],'UNKNOWN')

class HolderBoundTests(unittest.TestCase):
    def rows(self):return [dict(address=A(i+1),pinned_balance_base_units=str(100-i*10))for i in range(10)]
    def test_removed_holders_are_replaced_by_cutoff_not_silently_dropped(self):
        r=h.estimate(self.rows(),'500',[A(i+1)for i in range(7)])
        self.assertEqual(r['known_nonexcluded_share'],'0.12')
        self.assertEqual(r['per_address_top10_upper_bound'],'0.26')
        self.assertFalse(r['ranking_independently_verified']);self.assertFalse(r['buy_authorized'])
    def test_bad_ranking_missing_observations_duplicates_and_denominator_rejected(self):
        for change in ('rank','missing','duplicate','denominator'):
            rows=self.rows();den='1000'
            if change=='rank':rows[0],rows[1]=rows[1],rows[0]
            if change=='missing':rows.pop()
            if change=='duplicate':rows[-1]['address']=rows[0]['address']
            if change=='denominator':den='1'
            with self.assertRaises(ValueError):h.estimate(rows,den,[])
