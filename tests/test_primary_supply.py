import copy
import unittest
import primary_supply as p

class PrimarySupplyTests(unittest.TestCase):
    def raw(self):return dict(totalSupply=str(10**27),circulatingSupply=str(8*10**26),balances=[dict(address='0x'+'1'*40,balance=str(2*10**26))])
    def asset(self):return dict(network='eth',token_address=p.LINK)
    def test_exact_registered_contract_and_chain_required(self):
        def fail(_):self.fail('Unsupported assets must not fetch')
        for a in (dict(network='base',token_address=p.LINK),dict(network='eth',token_address='0x'+'2'*40)):
            self.assertEqual(p.collect(a,fail)['status'],'NOT_SUPPORTED')
    def test_issuer_reconciliation_is_not_an_audit(self):
        r=p.collect(self.asset(),lambda _:self.raw(),dict(circulating=800000000,total=1000000000))
        self.assertEqual(r['status'],'CORROBORATED_DISCLOSURE')
        self.assertFalse(r['metrics']['independent_onchain_balances_verified'])
        self.assertFalse(r['metrics']['complete_unlock_coverage_verified'])
        self.assertIsNone(r['provider_updated_at'])
        self.assertFalse(r['data_origin_independence_established'])
    def test_disagreement_is_preserved(self):
        r=p.collect(self.asset(),lambda _:self.raw(),dict(circulating=700000000,total=1000000000))
        self.assertEqual(r['status'],'CONFLICTING')
    def test_missing_duplicate_boolean_nonfinite_or_wrong_total_rejected(self):
        for change in ('missing','duplicate','bool','nan','total'):
            raw=self.raw()
            if change=='missing':raw['balances']=[]
            if change=='duplicate':raw['balances'].append(copy.deepcopy(raw['balances'][0]))
            if change=='bool':raw['circulatingSupply']=True
            if change=='nan':raw['circulatingSupply']='NaN'
            if change=='total':raw['totalSupply']='123'
            with self.assertRaises((ValueError,KeyError)):p.analyze(raw)
    def test_provider_failure_never_authorizes_anything(self):
        def bad(_):raise OSError('PRIVATE')
        r=p.collect(self.asset(),bad)
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('PRIVATE',str(r))
