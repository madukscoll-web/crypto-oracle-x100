import copy
import unittest
import urllib.error
from unittest.mock import patch

import evidence_coverage as coverage
import hourly_evidence
import solana_evidence as sol
import verification
import execution_quotes
import crypto_oracle_scanner as scanner
from provider_session import Session, ProviderUnavailable

MINT = 'So11111111111111111111111111111111111111112'
POOL = '11111111111111111111111111111111'


def item():
    return dict(network='solana', token_address=MINT, address=POOL, key='solana:'+POOL)


class SolanaTests(unittest.TestCase):
    def provider(self, authority=None, owner=sol.TOKEN_PROGRAM, supply='1000'):
        def request(url, payload):
            method = payload['method']
            if method == 'getGenesisHash':
                result = '5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d'
            elif method == 'getAccountInfo':
                self.assertEqual(payload['params'][0], MINT)
                self.assertEqual(payload['params'][1]['commitment'], 'finalized')
                result = dict(context=dict(slot=100), value=dict(owner=owner, executable=False,
                    data=dict(program='spl-token', parsed=dict(type='mint', info=dict(
                        supply=supply, decimals=9, isInitialized=True,
                        mintAuthority=authority, freezeAuthority=None)))))
            else:
                self.assertEqual(method, 'getTokenLargestAccounts')
                result = dict(context=dict(slot=101), value=[dict(address=POOL, amount='200', decimals=9)])
            return dict(jsonrpc='2.0', id=payload['id'], result=result)
        return request

    def test_finalized_mint_has_scoped_verified_claims_not_security_approval(self):
        result = sol.collect(item(), self.provider())
        self.assertEqual(result['onchain']['checks']['legacy_spl_mint_identity']['status'], 'VERIFIED')
        self.assertEqual(result['onchain']['metrics']['total_supply_base_units'], '1000')
        self.assertEqual(result['holders']['metrics']['listed_base_units'], '200')
        for field in ('holders', 'supply_comparison', 'contract_security'):
            self.assertEqual(result[field]['status'], 'UNKNOWN')
        for field in ('liquidity', 'sellability', 'execution'):
            self.assertEqual(result[field]['status'], 'UNSUPPORTED')
        self.assertFalse(scanner.telegram_eligible(dict(item(), verification=result)))

    def test_active_authority_is_adverse(self):
        result = sol.collect(item(), self.provider(authority=MINT))
        self.assertEqual(result['contract_security']['status'], 'FAIL')
        self.assertTrue(hourly_evidence.adverse(dict(verification=result)))

    def test_other_token_program_cannot_inherit_legacy_checks(self):
        result = sol.collect(item(), self.provider(owner='TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'))
        self.assertEqual(result['onchain']['status'], 'UNSUPPORTED')
        self.assertNotIn('checks', result['onchain'])

    def test_wrong_cluster_wrong_mint_type_and_malformed_supply(self):
        for kind in ('cluster', 'type', 'supply', 'missing_authority', 'duplicate_accounts'):
            original = self.provider()
            def request(url, payload):
                raw = original(url, payload)
                if kind == 'cluster' and payload['method'] == 'getGenesisHash': raw['result']='wrong'
                if payload['method'] == 'getAccountInfo':
                    parsed = raw['result']['value']['data']['parsed']
                    if kind == 'type': parsed['type']='account'
                    if kind == 'supply': parsed['info']['supply']=True
                    if kind == 'missing_authority': parsed['info'].pop('freezeAuthority')
                if kind == 'duplicate_accounts' and payload['method'] == 'getTokenLargestAccounts':
                    raw['result']['value'] *= 2
                return raw
            report = sol.collect(item(), request)
            self.assertEqual(report['holders' if kind == 'duplicate_accounts' else 'onchain']['status'], 'UNKNOWN')

    def test_outage_and_missing_provider_permission_are_distinct(self):
        for code, status in ((403, 'NOT_CHECKED'), (429, 'UNKNOWN'), (503, 'UNKNOWN')):
            def denied(url, payload):
                raise urllib.error.HTTPError(url, code, 'secret remote body', {}, None)
            result = sol.collect(item(), denied)
            self.assertEqual(result['onchain']['status'], status)
            self.assertNotIn('secret remote body', str(result))

    def test_case_sensitive_mint_and_invalid_identity_never_requested(self):
        calls=[]
        report=sol.collect(dict(item(), token_address='invalid'), lambda *args:calls.append(args))
        self.assertFalse(calls)
        self.assertEqual(report['onchain']['status'], 'UNKNOWN')


class CoverageTests(unittest.TestCase):
    def test_unsupported_chain_never_calls_evm_provider(self):
        calls=[]
        report=verification.collect(dict(network='unknown', token_address='0x'+'a'*40), lambda url:calls.append(url))
        self.assertEqual(report['integration']['status'], 'UNSUPPORTED')
        self.assertFalse(calls)

    def test_supported_goplus_network_does_not_call_unsupported_simulator(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            raise OSError('offline')
        report=verification.collect(dict(network='arbitrum', token_address='0x'+'a'*40, address='0x'+'b'*40),fetch)
        self.assertEqual(report['sellability']['status'],'UNSUPPORTED')
        self.assertTrue(any('/42161?' in url for url in calls))
        self.assertFalse(any('honeypot.is' in url for url in calls))

    def test_missing_execution_credentials_do_not_use_budget(self):
        calls=[]
        report=execution_quotes.collect(dict(network='base'),{},lambda *args:calls.append(args))
        self.assertEqual(report['status'],'NOT_CHECKED')
        self.assertFalse(calls)

    def test_legacy_partial_is_unknown_complete_gate(self):
        x=dict(verification=dict(contract_security=dict(status='LIMITED', reason='Screening only'),
             sellability=dict(status='FAIL',reason='Honeypot')))
        report=coverage.summary(x)
        self.assertEqual(report['contract_security']['status'],'UNKNOWN')
        self.assertEqual(report['sellability']['status'],'FAILED')
        self.assertEqual(report['holders']['status'],'NOT_CHECKED')
        self.assertFalse(scanner.telegram_eligible(x))

    def test_candidate_budget_retains_all_mandatory_gate_reasons(self):
        x=item()
        hourly_evidence.HourlyEvidence(max_candidates=0).collect(x)
        report=coverage.summary(x)
        self.assertEqual(set(report),set(coverage.GATES))
        self.assertTrue(all(r['status']=='NOT_CHECKED' and 'budget' in r['reason'] for r in report.values()))

    def test_per_candidate_budget_does_not_starve_next_candidate(self):
        s=Session(max_requests=4,transport=lambda *args:{},sleeper=lambda _:None)
        with s.budget(30,1):
            s.get('https://example.test/1')
            with self.assertRaises(ProviderUnavailable):s.get('https://example.test/2')
        s.get('https://example.test/3')
        self.assertEqual(s.requests,2)
        self.assertEqual(s.max_requests,4)

    def test_rotation_uses_persisted_check_time_and_deduplicates_token(self):
        a=dict(key='a',network='base',token_address='0xABC',score=100)
        b=dict(key='b',network='solana',token_address=MINT,score=80)
        c=dict(a,key='c')
        result=hourly_evidence.rotate([a,b,c],{'a':dict(evidence_checked_at='2026-10-30'), 'c':dict(evidence_checked_at='2026-10-30')})
        self.assertEqual([r['key'] for r in result],['b','a'])

    def test_token_dedup_covers_alternate_pools_but_not_chains(self):
        a=dict(key='base:pool1',network='base',token_address='0xABC')
        seen={scanner.token_alert_key(a)}
        self.assertTrue(scanner.already_alerted(dict(a,key='base:pool2',token_address='0xabc'),seen))
        self.assertFalse(scanner.already_alerted(dict(a,key='eth:pool2',network='eth'),seen))
        self.assertNotEqual(scanner.token_alert_key(item()),scanner.token_alert_key(dict(item(),token_address=MINT.lower())))

class AdapterBudgetTests(unittest.TestCase):
    def test_evm_budget_exhaustion_is_not_an_unexplained_unknown(self):
        import onchain
        import supply_evidence
        s=Session(max_requests=0)
        x=dict(network='base',token_address='0x'+'a'*40,address='0x'+'b'*40)
        with s:
            for collect in (onchain.collect, lambda x:supply_evidence.collect(x,s.get)):
                result=collect(x)
                self.assertEqual(result['status'],'NOT_CHECKED')
                self.assertIn('budget',result['reason'])
        self.assertEqual(s.requests,0)

    def test_unsupported_network_propagates_to_all_complete_gates(self):
        x=dict(network='unknown',verification=dict(integration=dict(status='UNSUPPORTED',reason='No reviewed chain adapter')))
        self.assertTrue(all(row['status']=='UNSUPPORTED' for row in coverage.summary(x).values()))

class SolanaGenesisTests(unittest.TestCase):
    def test_caip_prefix_is_not_the_full_rpc_genesis_hash(self):
        from asset_identity import CHAINS
        expected='5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d'
        self.assertEqual(sol.GENESIS,expected)
        self.assertNotEqual(sol.GENESIS,CHAINS['solana'].split(':',1)[1])
        calls=[]
        def prefix(url,payload):
            calls.append(payload)
            return dict(id=payload['id'],result=CHAINS['solana'].split(':',1)[1])
        report=sol.collect(item(),prefix)
        self.assertEqual(report['onchain']['status'],'UNKNOWN')
        self.assertEqual(len(calls),1)
