import datetime as dt
import hashlib
import unittest
from contract_sources import inspect
from custody_verification import owners
from supply_evidence import compare
from kyber_quotes import route,collect
from candidate_evidence import blockers
from live_candidate_scan import run

A,B,T=('0x'+c*40 for c in 'abc')
def abi_addr(a):return a[2:].zfill(64)
class SourceTests(unittest.TestCase):
    class Rpc:
        chain=1;block=dict(number='0x10')
        def call(self,*args):return '0x1234'
    def raw(self):
        return dict(address=A,chainId='1',runtimeMatch='match',runtimeBytecode=dict(onchainBytecode='0x1234'),
                    sources={'TokenTimelock.sol':{'content':'canonical'}},abi=[],proxyResolution=dict(isProxy=False),
                    compilation=dict(name='TokenTimelock'))
    def profile(self):return dict(compilation_name='TokenTimelock',files={'token/ERC20/utils/TokenTimelock.sol':dict(sha256=hashlib.sha256(b'canonical').hexdigest())})
    def test_canonical_source_not_independent_build_or_authority_audit(self):
        result=inspect(self.raw(),self.Rpc(),A,self.profile())
        self.assertTrue(result['runtime_source_match']);self.assertTrue(result['canonical_timelock_source'])
        self.assertFalse(result['independent_local_compiler_reproduction'])
        self.assertFalse(result['mint_and_upgrade_authority_audited'])
    def test_source_substitution_or_extra_code_not_canonical(self):
        raw=self.raw();raw['sources']['evil.sol']={'content':'override'}
        self.assertFalse(inspect(raw,self.Rpc(),A,self.profile())['canonical_timelock_source'])
    def test_chain_address_and_runtime_mismatch_rejected(self):
        for change in ('chain','address','code','match'):
            raw=self.raw()
            if change=='chain':raw['chainId']='56'
            elif change=='address':raw['address']=B
            elif change=='code':raw['runtimeBytecode']['onchainBytecode']='0xabcd'
            else:raw['runtimeMatch']='partial_match'
            with self.assertRaises(ValueError):inspect(raw,self.Rpc(),A,self.profile())

class CustodyTests(unittest.TestCase):
    def test_owner_array_and_duplicate_rejection(self):
        raw='0x'+format(32,'064x')+format(2,'064x')+abi_addr(A)+abi_addr(B)
        self.assertEqual(owners(raw),[A,B])
        with self.assertRaises(ValueError):owners(raw[:-64]+abi_addr(A))
        with self.assertRaises(ValueError):owners('0x00')

class SupplyTests(unittest.TestCase):
    def raw(self):return dict(platforms=dict(ethereum=A),last_updated='2026-10-21T20:00:00+00:00',
                               market_data=dict(total_supply=1000,circulating_supply=900,max_supply=None))
    def test_current_supply_never_means_future_coverage(self):
        now=dt.datetime(2026,10,21,20,tzinfo=dt.timezone.utc).timestamp()
        result=compare(self.raw(),1000000,3,'ethereum',A,now)
        self.assertEqual(result['relative_total_divergence'],'0')
        self.assertFalse(result['complete_vesting_and_mint_coverage'])
    def test_stale_wrong_identity_and_invalid_supply_rejected(self):
        now=dt.datetime(2026,10,21,20,tzinfo=dt.timezone.utc).timestamp()
        for kind in ('stale','identity','supply'):
            raw=self.raw()
            if kind=='stale':raw['last_updated']='2026-10-20T20:00:00+00:00'
            elif kind=='identity':raw['platforms']['ethereum']=B
            else:raw['market_data']['circulating_supply']=2000
            with self.assertRaises(ValueError):compare(raw,1000000,3,'ethereum',A,now)

class KyberTests(unittest.TestCase):
    def raw(self,sell=A,buy=B,amount=100):
        return dict(code=0,data=dict(routerAddress=T,routeSummary=dict(tokenIn=sell,tokenOut=buy,amountIn=str(amount),
            amountOut='200',gas='100',gasPrice='2',timestamp=str(int(dt.datetime.now(dt.timezone.utc).timestamp())),
            routerAddress=T,routeID='fixture',route=[[dict(pool=T)]])))
    def test_route_identity_staleness_and_code_type(self):
        route(self.raw(),A,B,100)
        raw=self.raw();raw['code']=False
        with self.assertRaises(ValueError):route(raw,A,B,100)
        raw=self.raw();raw['data']['routeSummary']['timestamp']='0'
        with self.assertRaises(ValueError):route(raw,A,B,100)
        with self.assertRaises(ValueError):route(self.raw(),B,A,100)
    def test_keyless_round_trip_uses_minimum_and_does_not_build_reference(self):
        calls=[]
        def transport(url,payload=None):
            self.assertIsNone(payload)
            from urllib.parse import urlparse,parse_qs
            q={k:v[0] for k,v in parse_qs(urlparse(url).query).items()};calls.append(q)
            return self.raw(q['tokenIn'],q['tokenOut'],int(q['amountIn']))
        result=collect(dict(network='eth',token_address=B,address=T),{},transport,reference_order=dict(funding_token=A,amount_base_units='100'))
        self.assertEqual(result['status'],'LIMITED');self.assertEqual(calls[1]['amountIn'],'198')
        self.assertFalse(result['raw'][0]['metrics']['funded_execution_verified'])
        self.assertFalse(result['raw'][0]['metrics']['minimum_output_enforcement_verified'])
    def test_calldata_build_is_not_funded_execution(self):
        count=[]
        def transport(url,payload=None):
            if payload is not None:
                self.assertEqual(payload['sender'],T);self.assertEqual(payload['slippageTolerance'],100)
                self.assertNotIn('permit',payload)
                count.append(1)
                return dict(code=0,data=dict(amountIn=payload['routeSummary']['amountIn'],amountOut='200',gas='100',
                    data='0x12345678',routerAddress=T,transactionValue='0'))
            from urllib.parse import urlparse,parse_qs
            q={k:v[0] for k,v in parse_qs(urlparse(url).query).items()}
            return self.raw(q['tokenIn'],q['tokenOut'],int(q['amountIn']))
        result=collect(dict(network='eth',token_address=B,address=T),
                       dict(ORACLE_FUNDING_TOKEN=A,ORACLE_ORDER_BASE_UNITS='100',ORACLE_TAKER_ADDRESS=T),transport)
        self.assertEqual(result['status'],'LIMITED');self.assertEqual(len(count),2)
        self.assertFalse(result['raw'][1]['metrics']['funded_execution_verified'])

class ScanTests(unittest.TestCase):
    def test_empty_or_failed_discovery_never_issues_buy(self):
        empty=run(('eth',),limit=1,delay=0,fetch=lambda url:{'data':[]})
        self.assertEqual(empty['assessed_candidate_count'],0);self.assertEqual(empty['verified_buy_signals'],[])
        def offline(url):raise OSError('offline')
        failed=run(('eth',),limit=1,delay=0,fetch=offline)
        self.assertEqual(len(failed['discovery_failures']),2)
        self.assertEqual(failed['verified_buy_signals'],[])
    def test_supply_conflict_is_an_explicit_mandatory_blocker(self):
        reasons=blockers(dict(verification=dict(supply_comparison=dict(status='CONFLICTING',reason='Totals differ'))))
        self.assertTrue(any('Supply evidence conflict: Totals differ' in x for x in reasons))
        self.assertTrue(any('Beneficial ownership' in x for x in reasons))

class AdverseLiveEvidenceTests(unittest.TestCase):
    def test_exact_pool_honeypot_overrides_other_provider_clearance(self):
        from crypto_oracle_scanner import decision_summary
        raw=dict(token=dict(address=A),chain=dict(id='56'),pairAddress=B,honeypotResult=dict(isHoneypot=True))
        item=dict(network='bsc',token_address=A,address=B,risk_category='RESEARCH CANDIDATE — LIMITED CHECKS',
                  verification=dict(sellability=dict(source='honeypot',status='FAIL',raw=raw)))
        self.assertEqual(decision_summary(item)[0],'DISCARD')
        raw['pairAddress']=T
        self.assertEqual(decision_summary(item)[0],'WAIT AND VERIFY')
    def test_conflicting_supply_is_a_failed_gate(self):
        import evidence_audit
        report=evidence_audit.audit(dict(verification=dict(supply_comparison=dict(status='CONFLICTING'))))
        self.assertIn('independent_supply_comparison',report['failures'])
        self.assertFalse(report['trade_ready'])


class SinkReconciliationTests(unittest.TestCase):
    def test_net_supply_match_is_not_circulating_or_burn_verification(self):
        from supply_evidence import sink_reconciliation
        from onchain import ZERO,DEAD
        r=sink_reconciliation('895',1000,0,{ZERO:0,DEAD:105})
        self.assertTrue(r['provider_total_matches_net_of_known_sinks'])
        self.assertFalse(r['burn_authority_or_circulating_supply_verified'])
    def test_mismatch_missing_or_impossible_sink_balances_do_not_reconcile(self):
        from supply_evidence import sink_reconciliation
        from onchain import ZERO,DEAD
        self.assertFalse(sink_reconciliation('800',1000,0,{ZERO:0,DEAD:105})['provider_total_matches_net_of_known_sinks'])
        for bad in ({DEAD:105},{ZERO:True,DEAD:105},{ZERO:800,DEAD:800}):
            with self.assertRaises(ValueError):sink_reconciliation('895',1000,0,bad)
