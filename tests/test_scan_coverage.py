import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from provider_session import Session,ProviderUnavailable
from onchain import verify_pair,verify_v3_pool
from live_candidate_scan import select_candidates,update_counts,write_report
from custody_verification import collect as custody

A,B,P,F=('0x'+c*40 for c in 'abcd')
def word(n):return '0x'+format(n,'064x')
def addr(a):return '0x'+a[2:].zfill(64)

class SessionTests(unittest.TestCase):
    def test_permission_and_payment_failures_are_not_retried(self):
        for status in (401,402,403):
            calls=[]
            def deny(*args):
                calls.append(1);raise urllib.error.HTTPError(args[0],status,'denied',{},None)
            s=Session(transport=deny)
            with self.assertRaises(urllib.error.HTTPError):s.json('https://provider.example/a',headers={'x-api-key':'secret-fixture'})
            with self.assertRaises(ProviderUnavailable):s.get('https://provider.example/b')
            self.assertEqual(len(calls),1);self.assertNotIn('secret-fixture',str(s.summary()))
    def test_retry_after_is_never_shortened(self):
        now=[100.]
        def provider(url,*args):
            raise urllib.error.HTTPError(url,429,'limited',{'Retry-After':'180'},None)
        session=Session(transport=provider,clock=lambda:now[0],sleeper=lambda _:None)
        with self.assertRaises(urllib.error.HTTPError):session.get('https://provider.example/a')
        self.assertEqual(session.cooldown['provider.example'],280)
        self.assertFalse(session.wait_ready('https://provider.example/a'))

    def test_missing_resource_does_not_disable_other_resources(self):
        def provider(url,*args):
            if url.endswith('/a'):raise urllib.error.HTTPError(url,404,'missing',{},None)
            return {'data':1}
        s=Session(transport=provider,sleeper=lambda _:None)
        with self.assertRaises(urllib.error.HTTPError):s.get('https://provider.example/a')
        with self.assertRaises(ProviderUnavailable):s.get('https://provider.example/a')
        self.assertEqual(s.get('https://provider.example/b'),{'data':1})
    def test_rate_limit_cooldown_and_request_budget(self):
        now=[100.]
        def provider(url,*args):raise urllib.error.HTTPError(url,429,'limited',{},None)
        s=Session(transport=provider,clock=lambda:now[0],sleeper=lambda _:None)
        with self.assertRaises(urllib.error.HTTPError):s.get('https://provider.example/a')
        with self.assertRaises(ProviderUnavailable):s.get('https://provider.example/b')
        self.assertEqual(s.requests,1)
        s=Session(max_requests=1,transport=lambda *args:{},sleeper=lambda _:None)
        s.get('https://provider.example/a')
        with self.assertRaises(ProviderUnavailable):s.get('https://other.example/a')

class ChainCoverageTests(unittest.TestCase):
    def test_bsc_pair_queries_its_actual_factory(self):
        factory='0xca143ce32fe78f1f7019d7d551a6402fc5350c73'
        parent=self
        class Rpc:
            chain=56;block={'number':'0x10'}
            def call(self,*args):return '0x1234'
            def read(self,to,sel,args=''):
                if sel=='0dfe1681':return addr(A)
                if sel=='d21220a7':return addr(B)
                if sel=='c45a0155':return addr(factory)
                if sel=='e6a43905':parent.assertEqual(to,factory);return addr(P)
                if sel=='18160ddd':return word(100)
                if sel=='0902f1ac':return word(20)+word(30)[2:]+word(1)[2:]
                raise AssertionError(sel)
            def balance(self,*args):return 0
        result=verify_pair(Rpc(),P,A)
        self.assertEqual(result['protocol'],'PancakeV2');self.assertFalse(result['lock_coverage_complete'])
    def test_base_v3_does_not_masquerade_as_locked_erc20_lp(self):
        factory='0x33128a8fc17869897dce68ed026d694621f6fdfd'
        class Rpc:
            chain=8453
            def read(self,to,sel,args=''):
                return {'c45a0155':addr(factory),'0dfe1681':addr(A),'d21220a7':addr(B),
                        'ddca3f43':word(500),'1698ee82':addr(P),'1a686502':word(100)}[sel]
        result=verify_v3_pool(Rpc(),P,A)
        self.assertEqual(result['position_type'],'concentrated_nft')
        self.assertFalse(result['lock_coverage_complete']);self.assertNotIn('burned_lp_fraction',result)
    def test_base_safe_signers_are_not_beneficial_owners(self):
        class Rpc:
            url='https://rpc.example';calls=[]
            def snapshot(self):return {'number':'0x10'}
            def unchanged(self):pass
            def checksum(self,value):return value
            def call(self,*args):return '0x1234'
            def read(self,to,sel,*args):
                if sel=='8da5cb5b':return addr(A)
                if sel=='a0e67e2b':return word(32)+word(1)[2:]+addr(A)[2:]
                if sel=='e75235b8':return word(1)
        urls=[]
        def fetch(url):urls.append(url);return dict(address=B,owners=[A],threshold=1)
        result=custody(dict(network='base',token_address=P),[dict(address=B)],fetch,Rpc())
        self.assertTrue(urls[0].startswith('https://safe-transaction-base.safe.global/'))
        self.assertEqual(result['raw']['records'][0]['onchain_owners'],[A])
        self.assertFalse(result['raw']['token_authority']['beneficial_identity_verified'])

class AccountingTests(unittest.TestCase):
    def test_chain_token_diversity_and_no_duplicate_assessments(self):
        items=[dict(network=n,key=n+':'+str(i),discovery_token_hint=t,pool_class='NEW POOL')
               for n,i,t in [('eth',1,'a'),('eth',2,'a'),('base',1,'b'),('bsc',1,'c')]]
        result=select_candidates(items,('eth','base','bsc'),10)
        self.assertEqual(len(result),3);self.assertEqual({x['network'] for x in result},{'eth','base','bsc'})
    def test_counts_partition_security_decisions_from_discovery_filters(self):
        result=dict(discovery=[dict(raw=dict(data=[{}, {}, {}, {}]))],candidates=[dict(key='a',decision='DISCARD'),dict(key='b',decision='WAIT AND VERIFY')])
        update_counts(result,{'a','b','c','d'},{'a':{},'b':{},'c':{}})
        self.assertEqual(result['counts']['rejected_assessed_pools'],1)
        self.assertEqual(result['counts']['still_unverified_assessed_pools'],1)
        self.assertEqual(result['counts']['unassessed_qualified_pools'],1)
        self.assertEqual(result['counts']['discovery_filtered_out_unique_pools'],1)
        self.assertEqual(result['counts']['not_verified_discovered_pools'],3)
    def test_compressed_checkpoint_is_lossless(self):
        import gzip
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'scan.json.gz';write_report(path,dict(status='IN_PROGRESS',candidates=[]))
            with gzip.open(path,'rt') as stream:self.assertEqual(json.load(stream)['status'],'IN_PROGRESS')

class CoverageSafetyTests(unittest.TestCase):
    def test_verification_only_cannot_qualify_even_with_verification_flags(self):
        from crypto_oracle_scanner import decision_summary
        action,reason=decision_summary(dict(discovery_eligible=False,sellability_verified=True,
            executable_quote_verified=True,risk_category='RESEARCH CANDIDATE — LIMITED CHECKS'))
        self.assertEqual(action,'WAIT AND VERIFY');self.assertIn('verification-only',reason)
    def test_checksum_uses_keccak_rpc_not_sha3_or_lowercase_query(self):
        from onchain import Rpc
        requests=[]
        def transport(payload):
            requests.append(payload);return dict(jsonrpc='2.0',id=payload['id'],result='0x'+'f'*64)
        rpc=Rpc('base',transport)
        self.assertEqual(rpc.checksum(A),'0x'+'A'*40)
        self.assertEqual(requests[0]['method'],'web3_sha3')
        self.assertEqual(bytes.fromhex(requests[0]['params'][0][2:]).decode(),'a'*40)
    def test_denied_host_never_waits_and_rate_recovery_waits_once(self):
        now=[100.];sleeps=[]
        def sleep(seconds):sleeps.append(seconds);now[0]+=seconds
        s=Session(clock=lambda:now[0],sleeper=sleep);s.denied['p.example']=403
        self.assertFalse(s.wait_ready('https://p.example/a'))
        s.cooldown['r.example']=150.
        self.assertTrue(s.wait_ready('https://r.example/a'))
        self.assertFalse(s.wait_ready('https://r.example/b'));self.assertEqual(sleeps,[50.])
