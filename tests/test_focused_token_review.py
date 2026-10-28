import copy
import unittest
from unittest.mock import patch
import focused_token_review as f
import primary_supply

A='0x'+'1'*40
B='0x'+'2'*40

class FakeRpc:
    url='https://rpc.example';chain=1
    def __init__(self,*args):self.calls=[];self.balances={A:2*10**26};self.checked=False
    def snapshot(self):self.block=dict(number='0x1',hash='0x'+'a'*64);return self.block
    def read(self,token,selector):
        if selector=='8da5cb5b':raise ValueError('no owner method')
        return '0x'+format(10**27 if selector=='18160ddd' else 18,'064x')
    def balance(self,token,owner):self.calls.append(owner);return self.balances.get(owner,0)
    def unchanged(self):self.checked=True

class FocusedReviewTests(unittest.TestCase):
    def raw(self):return dict(totalSupply=str(10**27),circulatingSupply=str(8*10**26),balances=[dict(address=A,balance=str(2*10**26))])
    def holders(self):return dict(holders=[dict(address=A,balance='200000000'),dict(address=B,balance='0')])
    def test_every_issuer_wallet_is_read_with_exact_arithmetic(self):
        rpc=FakeRpc();r=f.disclosure_balances(self.raw(),rpc,primary_supply.LINK)
        self.assertEqual(rpc.calls,[A]);self.assertTrue(r['exact_balance_match']);self.assertTrue(r['exact_circulation_match'])
        self.assertFalse(r['circulation_definition_verified']);self.assertFalse(r['release_restrictions_verified'])
    def test_balance_drift_is_not_silently_accepted_as_exact_match(self):
        rpc=FakeRpc();rpc.balances[A]+=100
        r=f.disclosure_balances(self.raw(),rpc,primary_supply.LINK)
        self.assertFalse(r['exact_balance_match']);self.assertFalse(r['exact_circulation_match'])
        self.assertEqual(r['source_circulation_delta_base_units'],'-100')
    def test_malformed_source_and_holder_duplicates_fail(self):
        raw=self.raw();raw['balances'].append(copy.deepcopy(raw['balances'][0]))
        with self.assertRaises(ValueError):f.disclosure_balances(raw,FakeRpc(),primary_supply.LINK)
        h=self.holders();h['holders'].append(copy.deepcopy(h['holders'][0]))
        with self.assertRaises(ValueError):f.holders_at_block(h,FakeRpc(),primary_supply.LINK)
    def test_holder_balances_and_labels_do_not_prove_complete_ranking(self):
        r=f.holders_at_block(self.holders(),FakeRpc(),primary_supply.LINK,[A])
        self.assertEqual(r['listed_fraction_of_gross_supply'],'0.2');self.assertEqual(r['issuer_label_matches'],1)
        self.assertIsNone(r['adjusted_top10_fraction']);self.assertFalse(r['beneficial_owners_verified'])
        self.assertFalse(r['ranking_completeness_verified'])
    def test_source_match_inventory_is_not_authority_audit(self):
        r=f.authority_surface(dict(status='LIMITED',metrics=dict(runtime_source_match=True,exposed_functions=['transfer','mint','owner','upgradeTo'])))
        self.assertEqual(r['status'],'SOURCE_BOUND_INVENTORY');self.assertIn('mint',r['named_authority_surfaces'])
        self.assertFalse(r['authority_audit_completed'])
        self.assertEqual(f.authority_surface(dict(status='UNKNOWN',metrics=dict(runtime_source_match=True)))['status'],'UNKNOWN')
    def test_reorganized_snapshot_discards_provisional_wallet_findings(self):
        class Reorg(FakeRpc):
            def unchanged(self):raise ValueError('reorg')
        asset=f.TOKENS[0]
        def fetch(url):
            if url==primary_supply.URL:return self.raw()
            return dict(code=1,result={primary_supply.LINK:self.holders()})
        with patch.object(f,'Rpc',Reorg),patch.object(f.contract_sources,'collect',return_value=dict(status='UNKNOWN')):
            r=f.review(asset,fetch)
        self.assertTrue(r['errors']);self.assertNotIn('holders',r['evidence']);self.assertNotIn('issuer_wallet_pinning',r['evidence'])
        self.assertFalse(r['buy_authorized'])
    def test_missing_owner_method_never_claims_renounced_ownership(self):
        def fetch(url):
            if url==primary_supply.URL:return self.raw()
            return dict(code=1,result={primary_supply.LINK:self.holders()})
        with patch.object(f,'Rpc',FakeRpc),patch.object(f.contract_sources,'collect',return_value=dict(status='UNKNOWN')):
            r=f.review(f.TOKENS[0],fetch)
        self.assertEqual(r['evidence']['owner_observation']['status'],'UNKNOWN');self.assertFalse(r['buy_authorized'])
    def test_transport_error_is_safe_and_stays_incomplete(self):
        def fetch(_):raise OSError('PRIVATE')
        with patch.object(f.contract_sources,'collect',return_value=dict(status='UNKNOWN')):
            r=f.review(f.TOKENS[0],fetch)
        self.assertEqual(r['status'],'INCOMPLETE');self.assertNotIn('PRIVATE',str(r));self.assertFalse(r['buy_authorized'])
