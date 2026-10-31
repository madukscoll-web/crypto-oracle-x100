"""Synthetic signed review fixtures ONLY. No fixture key enters production trust."""
import base64
import copy
import datetime as dt
import hashlib
import pathlib
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import authenticated_admission as admission
import canonical_outcomes
import crypto_oracle_scanner as scanner
import evidence_audit
import investment_gates
import opportunity_alerts
from sequential_simulation import TRANSFER, request_for

NOW=1800000000
TOKEN,POOL,FUNDING,TARGET,TAKER=('0x'+c*40 for c in '12345')
CODE='0x6000'
CODEHASH=hashlib.sha256(bytes.fromhex(CODE[2:])).hexdigest()
def at(seconds=0):return dt.datetime.fromtimestamp(NOW+seconds,dt.timezone.utc).isoformat()
def topic(a):return '0x'+a[2:].zfill(64)
def event(token,src,dst,n):return dict(address=token,topics=[TRANSFER,topic(src),topic(dst)],data='0x'+format(n,'064x'))
def read(n):return dict(status='0x1',returnData='0x'+format(n,'064x'))

def fixture():
    def leg(sell,buy,amount,out):
        return dict(observed_at=at(),expires_at=at(60),pools=[POOL],router_bytecode=CODE,raw=dict(
            liquidityAvailable=True,sellToken=sell,buyToken=buy,sellAmount=str(amount),buyAmount=str(out),minBuyAmount=str(out),blockNumber='16',
            transaction=dict(to=TARGET,data='0x12345678',gas='100000',gasPrice='1',value='0'),
            fees=dict(zeroExFee=None,integratorFee=None,gasFee=None),issues=dict(simulationIncomplete=False,balance=None,allowance=None)))
    simulation=[dict(calls=[read(0),read(100),
        dict(status='0x1',gasUsed='0x100',logs=[event(FUNDING,TAKER,POOL,100),event(TOKEN,POOL,TAKER,200)]),
        read(200),read(0),
        dict(status='0x1',gasUsed='0x100',logs=[event(TOKEN,TAKER,POOL,200),event(FUNDING,POOL,TAKER,99)]),read(0),read(99)])]
    controls={name:'ABSENT' for name in admission.CONTROLS};controls['bridge_backing']='NOT_APPLICABLE_NATIVE_ASSET'
    metrics=dict(
        security=dict(runtime_sha256=CODEHASH,runtime_bytecode=CODE,controls=controls,buy_tax_percent='0',sell_tax_percent='0',transfer_tax_percent='0'),
        lp_controls=dict(pool=POOL,withdrawal_authority='NO_UNCOVERED_AUTHORITY',total_units='1000',burned_units='1000',locked_units='0'),
        holders=dict(coverage='COMPLETE_BENEFICIAL_OWNERSHIP',total_units='10000',excluded_units='0',owners=[dict(owner_id=str(i),units='100') for i in range(100)]),
        tokenomics=dict(circulating_units='10000',total_units='10000',max_units='10000',coverage='COMPLETE_ALLOCATIONS_AND_ENFORCEABLE_VESTING',
            allocations=dict(circulating='10000',team='0',treasury='0',other_locked='0'),schedules=[],unlock_coverage_start=at(-10),unlock_coverage_end=at(366*86400),unlock_30d_units='0',market_cap_usd='5000',fdv_usd='5000'),
        execution=dict(block_hash='0x'+'b'*64,pool=POOL,runtime_sha256=CODEHASH,snapshot={'number':'0x10','hash':'0x'+'b'*64,'timestamp':hex(NOW)},quotes=[leg(FUNDING,TOKEN,100,200),leg(TOKEN,FUNDING,200,99)],
            simulation=simulation,taker=TAKER,simulation_method='eth_simulateV1',simulation_mode='VALIDATION_NO_OVERRIDES',
            order_usd='100',minimum_exit_usd='99',gas_usd='.001',fees_usd='.01',executable_depth_usd='100000',price_impact_percent='.1',spread_percent='.1',equity_usd='10000',funding_decimals=0,funding_price_usd='1',native_price_usd='2000'))
    metrics['execution']['simulation_request']=request_for(metrics['execution']['quotes'],TAKER)
    evidence={}
    for name,values in metrics.items():
        sources=[]
        for org in ('provider-one','provider-two'):
            raw=dict(metrics=copy.deepcopy(values))
            sources.append(dict(provider=org,organization=org,url='https://'+org+'.example/report',network='eth',contract=TOKEN,status='VERIFIED',conflict='NONE',observed_at=at(),raw=raw,sha256=hashlib.sha256(admission.canonical(raw)).hexdigest()))
        evidence[name]=dict(verdict='PASS',metrics=values,sources=sources)
    return dict(payload=dict(schema=admission.VERSION,entry_status='READY',observed_at=at(),expires_at=at(60),identity=dict(network='eth',token=TOKEN,pool=POOL,funding=FUNDING,block_number='16',block_timestamp=at(),block_hash='0x'+'b'*64,runtime_sha256=CODEHASH),evidence=evidence),signatures=[])


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='oracle-test-keys-')
        cls.root=pathlib.Path(cls.directory.name);cls.trust=dict(schema=admission.VERSION,reviewers={},sources={org+'.example':{'organization':org} for org in ('provider-one','provider-two')})
        cls.trust['routers']={'eth:'+TARGET:{'runtime_sha256':CODEHASH,'selectors':['0x12345678']}}
        for i in (1,2):
            key=cls.root/str(i)
            subprocess.run(['openssl','genpkey','-algorithm','Ed25519','-out',str(key)],check=True,capture_output=True)
            public=subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],check=True,capture_output=True).stdout.decode()
            cls.trust['reviewers'][str(i)]=dict(public_key=public,organization='independent-reviewer-'+str(i),revoked=False,valid_from=at(-100),valid_until=at(86400),scopes=list(admission.SECTIONS))
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()
    def setUp(self):
        self.bundle=fixture()
        self.item=dict(network='eth',token_address=TOKEN,address=POOL,quote_token_address=FUNDING,admission_bundle=self.bundle)
        self.policy=patch.object(admission,'load_trust',return_value=copy.deepcopy(self.trust));self.policy.start();self.addCleanup(self.policy.stop)
    def sign(self):
        # Reconcile raw source observations only in clearly synthetic fixtures.
        for section in self.bundle['payload']['evidence'].values():
            for source in section['sources']:
                source['raw']['metrics']=copy.deepcopy(section['metrics'])
                source['sha256']=hashlib.sha256(admission.canonical(source['raw'])).hexdigest()
        (self.root/'payload').write_bytes(admission.canonical(self.bundle['payload']))
        self.bundle['signatures']=[]
        for i in (1,2):
            signature=subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.root/str(i)),'-rawin','-in',str(self.root/'payload')],check=True,capture_output=True).stdout
            self.bundle['signatures'].append(dict(reviewer=str(i),signature=base64.b64encode(signature).decode()))
    def evaluate(self):return admission.evaluate(self.item,now=NOW)
    def test_complete_independently_signed_fixture_passes(self):
        self.sign();result=self.evaluate()
        self.assertTrue(result['admitted'],result)
        self.assertEqual(set(result['checks'].values()),{'PASS'})
        self.assertFalse(result['orders_allowed'])
        self.assertEqual(result['reviewers'],['1','2'])
    def test_unsigned_and_caller_keys_cannot_admit(self):
        self.item.update(buy_eligible=True,verified=True,trust_registry=self.trust)
        self.assertFalse(self.evaluate()['admitted'])
        self.sign()
        with patch.object(admission,'load_trust',return_value=dict(schema=admission.VERSION,reviewers={})):
            self.assertFalse(self.evaluate()['admitted'])
    def test_tamper_after_signature(self):
        self.sign();self.bundle['payload']['evidence']['tokenomics']['metrics']['circulating_units']='999999'
        self.assertFalse(self.evaluate()['admitted'])
    def test_duplicate_same_organization_revoked_and_expired_reviewers(self):
        self.sign()
        for change in ('duplicate','organization','revoked','expired','scope'):
            with self.subTest(change=change):
                trust=copy.deepcopy(self.trust);original=copy.deepcopy(self.bundle['signatures'])
                if change=='duplicate':self.bundle['signatures'][1]=self.bundle['signatures'][0]
                if change=='organization':trust['reviewers']['2']['organization']=trust['reviewers']['1']['organization']
                if change=='revoked':trust['reviewers']['2']['revoked']=True
                if change=='expired':trust['reviewers']['2']['valid_until']=at(-1)
                if change=='scope':trust['reviewers']['2']['scopes']=['security']
                with patch.object(admission,'load_trust',return_value=trust):self.assertFalse(self.evaluate()['admitted'])
                self.bundle['signatures']=original
    def test_every_missing_mandatory_section_blocks(self):
        original=copy.deepcopy(self.bundle)
        for name in admission.SECTIONS:
            with self.subTest(section=name):
                self.bundle.clear();self.bundle.update(copy.deepcopy(original));del self.bundle['payload']['evidence'][name]
                self.sign();self.assertFalse(self.evaluate()['admitted'])
    def test_signed_but_inconsistent_or_adverse_evidence_cannot_admit(self):
        original=copy.deepcopy(self.bundle)
        mutations=[('security','controls',{'honeypot':'ABSENT'}),('security','sell_tax_percent','50'),
            ('lp_controls','burned_units','999'),('lp_controls','withdrawal_authority','OWNER'),
            ('holders','excluded_units','1000'),('holders','coverage','PARTIAL'),
            ('tokenomics','circulating_units','20000'),('tokenomics','unlock_30d_units','2000'),
            ('tokenomics','market_cap_usd','1'),('tokenomics','unlock_coverage_end',at(10)),
            ('execution','minimum_exit_usd','100'),('execution','executable_depth_usd','1'),
            ('execution','gas_usd','0'),('execution','equity_usd','1'),('execution','simulation_mode','STATE_OVERRIDES')]
        for section,field,value in mutations:
            with self.subTest(section=section,field=field):
                self.bundle.clear();self.bundle.update(copy.deepcopy(original))
                self.bundle['payload']['evidence'][section]['metrics'][field]=value
                self.sign();self.assertFalse(self.evaluate()['admitted'])
    def test_wrong_chain_contract_pool_and_funding_block(self):
        self.sign()
        for field,value in [('network','base'),('token_address',TARGET),('address',TARGET),('quote_token_address',TARGET)]:
            item=dict(self.item);item[field]=value
            self.assertFalse(admission.evaluate(item,now=NOW)['admitted'])
    def test_stale_and_future_bundles_block(self):
        self.sign()
        for when in (NOW-1,NOW+60,NOW+61):self.assertFalse(admission.evaluate(self.item,now=when)['admitted'])
    def test_failed_sell_balance_or_log_cannot_admit(self):
        for index in (5,7):
            self.bundle=fixture();self.item['admission_bundle']=self.bundle
            calls=self.bundle['payload']['evidence']['execution']['metrics']['simulation'][0]['calls']
            if index==5:calls[index]['status']='0x0'
            else:calls[index]['returnData']='0x'+format(0,'064x')
            self.sign();self.assertFalse(self.evaluate()['admitted'])
    def test_existing_adverse_evidence_always_vetoes_signed_bundle(self):
        self.sign();self.item['verification']={'sellability':{'status':'FAIL'}}
        self.assertFalse(self.evaluate()['admitted'])
    def test_complete_pipeline_to_confirmed_telegram_receipt(self):
        self.sign()
        # Freeze only the evaluator's clock; signatures and all evidence validators
        # remain real. Transport is explicitly synthetic and sends no live message.
        evaluate=admission.evaluate
        with patch.object(admission,'evaluate',side_effect=lambda item,now=None:evaluate(item,now=NOW)):
            self.assertTrue(evidence_audit.audit(self.item)['trade_ready'])
            self.assertEqual(scanner.decision_summary(self.item)[0],'BUY CANDIDATE — REVIEW ENTRY')
            self.assertTrue(scanner.validate_execution_evidence(self.item))
            self.assertTrue(scanner.telegram_eligible(self.item))
            canonical=canonical_outcomes.assess(self.item,now=NOW)
            self.assertEqual(canonical['outcome'],'BUY CANDIDATE — MANUAL REVIEW')
            self.assertFalse(canonical['orders_allowed'])
            result=opportunity_alerts.classify(self.item,now=NOW)
            self.assertTrue(result['eligible_for_buy']);self.assertEqual(result['missing_checks'],[])
            self.assertTrue(investment_gates.assess(self.item,now=dt.datetime.fromtimestamp(NOW,dt.timezone.utc))['buy_eligible'])
            message=opportunity_alerts.format_admission_alert(self.item)
            self.assertIn('MANUAL REVIEW',message);self.assertIn('minimum_exit_usd',message)
            self.assertIn('Automatic trading DISABLED',message)
            self.assertLessEqual(len(message.encode('utf-16-le'))//2,4096)
            self.assertNotIn('UNVERIFIED RESEARCH LEAD',message)
            calls=[]
            def transport(token,method,data):
                calls.append(method)
                return {'ok':True,'result':{'id':123}} if method=='getChat' else {'ok':True,'result':{'message_id':99,'chat':{'id':123}}}
            self.assertTrue(opportunity_alerts.deliver(self.item,result,'SYNTHETIC TEST',{'TELEGRAM_BOT_TOKEN':'fixture-only','TELEGRAM_CHAT_ID':'123'},transport=transport,parts=[message]))
            self.assertEqual(calls,['getChat','sendMessage'])
            with patch.dict(os.environ,TELEGRAM_BOT_TOKEN='fixture-only',TELEGRAM_CHAT_ID='123'), patch.object(scanner,'send_message',return_value=True) as send:
                self.assertTrue(scanner.send_telegram(self.item))
                self.assertIn('MANUAL REVIEW',send.call_args.args[0])
    def test_sources_must_be_independent_fresh_and_consistent(self):
        original=copy.deepcopy(self.bundle)
        for mutation in ('same_org','stale','digest','conflict','metrics'):
            with self.subTest(mutation=mutation):
                self.bundle.clear();self.bundle.update(copy.deepcopy(original))
                sources=self.bundle['payload']['evidence']['security']['sources']
                if mutation=='same_org':sources[1]['organization']=sources[0]['organization']
                if mutation=='stale':sources[1]['observed_at']=at(-90000)
                if mutation=='conflict':sources[1]['conflict']='CONFLICTING'
                self.sign()
                if mutation in ('digest','metrics'):
                    # Re-sign the malformed source itself, not just a transport
                    # mutation, to exercise semantic checks after authentication.
                    sources[0]['raw']['metrics']['sell_tax_percent']='99'
                    if mutation=='metrics':sources[0]['sha256']=hashlib.sha256(admission.canonical(sources[0]['raw'])).hexdigest()
                    self.resign_without_reconciling()
                self.assertFalse(self.evaluate()['admitted'])
    def resign_without_reconciling(self):
        (self.root/'payload').write_bytes(admission.canonical(self.bundle['payload']))
        for i,signed in enumerate(self.bundle['signatures'],1):
            signed['signature']=base64.b64encode(subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.root/str(i)),'-rawin','-in',str(self.root/'payload')],check=True,capture_output=True).stdout).decode()
    def test_fees_and_simulation_overrides_cannot_be_hidden(self):
        for mutation in ('fees','override','route','expired','l2_fee'):
            with self.subTest(mutation=mutation):
                self.bundle=fixture();self.item['admission_bundle']=self.bundle
                execution=self.bundle['payload']['evidence']['execution']['metrics']
                if mutation=='fees':execution['quotes'][0]['raw']['fees']['zeroExFee']={'token':FUNDING,'amount':'20'}
                if mutation=='override':execution['simulation_request']['blockStateCalls'][0]['stateOverrides']={TAKER:{'balance':'0xffff'}}
                if mutation=='route':execution['quotes'][1]['pools']=[TARGET]
                if mutation=='expired':execution['quotes'][1]['expires_at']=at()
                if mutation=='l2_fee':
                    self.item['network']='base';self.bundle['payload']['identity']['network']='base'
                    for section in self.bundle['payload']['evidence'].values():
                        for source in section['sources']:source['network']='base'
                self.sign();self.assertFalse(self.evaluate()['admitted'])
                self.item['network']='eth'
    def test_unresolved_conflicts_and_research_only_modes_block(self):
        self.sign()
        for extra in ({'evidence_review':{'supply':{'circulating_supply':{'status':'CONFLICTING'}}}},
                      {'evidence_review':{'security':{'status':'HIGH CONCERN'}}},
                      {'market_corroboration':{'status':'CONFLICTING'}},
                      {'refresh_failed':True},{'discovery_eligible':False},{'scan_mode':'verification_only'}):
            item=dict(self.item,**extra)
            self.assertFalse(admission.evaluate(item,now=NOW)['admitted'])
    def test_missing_openssl_fails_closed(self):
        self.sign()
        with patch.object(admission.subprocess,'run',side_effect=FileNotFoundError):
            self.assertFalse(self.evaluate()['admitted'])
    def test_authenticated_monitoring_stays_watchlist_without_buy_authority(self):
        self.bundle['payload']['entry_status']='MONITOR';self.sign()
        result=self.evaluate()
        self.assertTrue(result['safety_verified']);self.assertFalse(result['admitted'])
        evaluate=admission.evaluate
        with patch.object(admission,'evaluate',side_effect=lambda item,now=None:evaluate(item,now=NOW)):
            self.assertEqual(canonical_outcomes.assess(self.item,now=NOW)['outcome'],'WATCHLIST')
            self.assertTrue(scanner.telegram_eligible(self.item))
            self.assertFalse(evidence_audit.audit(self.item)['trade_ready'])
    def test_one_enrolled_key_cannot_claim_two_independent_reviewer_roles(self):
        self.sign();trust=copy.deepcopy(self.trust)
        trust['reviewers']['2']['public_key']=trust['reviewers']['1']['public_key']
        self.bundle['signatures'][1]['signature']=self.bundle['signatures'][0]['signature']
        with patch.object(admission,'load_trust',return_value=trust):self.assertFalse(self.evaluate()['admitted'])
    def test_unchanged_watch_is_silent_but_promotion_can_notify(self):
        self.item['key']='eth:'+POOL
        self.bundle['payload']['entry_status']='MONITOR';self.sign()
        evaluate=admission.evaluate
        with patch.object(admission,'evaluate',side_effect=lambda item,now=None:evaluate(item,now=NOW)):
            seen={scanner.decision_alert_key(self.item)}
            self.assertTrue(scanner.already_alerted(self.item,seen))
            self.bundle['payload']['entry_status']='READY';self.sign()
            self.assertFalse(scanner.already_alerted(self.item,seen))
            seen.add(scanner.decision_alert_key(self.item))
            self.assertTrue(scanner.already_alerted(self.item,seen))
    def test_matching_fake_cap_ratios_do_not_hide_quote_price_conflict(self):
        metrics=self.bundle['payload']['evidence']['tokenomics']['metrics']
        metrics['market_cap_usd']=metrics['fdv_usd']='1000000'
        self.sign();self.assertFalse(self.evaluate()['admitted'])
    def test_bytecode_and_pinned_rpc_snapshot_must_match_signed_identity(self):
        for mutation in ('bytecode','snapshot'):
            self.bundle=fixture();self.item['admission_bundle']=self.bundle
            if mutation=='bytecode':self.bundle['payload']['evidence']['security']['metrics']['runtime_bytecode']='0x6001'
            else:self.bundle['payload']['evidence']['execution']['metrics']['snapshot']['hash']='0x'+'c'*64
            self.sign();self.assertFalse(self.evaluate()['admitted'])
    def test_exact_asset_file_intake_uses_real_signature_verification(self):
        import json
        self.sign();item=dict(self.item);item.pop('admission_bundle')
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'admission_evidence').mkdir()
            identity={'network':item['network'],'token':item['token_address'],'pool':item['address']}
            filename=hashlib.sha256(admission.canonical(identity)).hexdigest()+'.json'
            (root/'admission_evidence'/filename).write_text(json.dumps(self.bundle))
            with patch.object(admission,'ROOT',root):
                self.assertTrue(admission.evaluate(item,now=NOW)['admitted'])
                self.assertFalse(admission.evaluate(item,now=NOW+60)['admitted'])
    def test_signed_feed_intake_remains_bound_to_production_trust(self):
        import admission_feed
        self.sign();item=dict(self.item);item.pop('admission_bundle')
        trust=copy.deepcopy(self.trust);trust['bundle_endpoint']='https://review-publisher.example/bundle'
        admission_feed._CACHE.clear()
        with patch.object(admission,'load_trust',return_value=trust),patch.object(admission_feed,'fetch',return_value=self.bundle) as fetch:
            self.assertTrue(admission.evaluate(item,now=NOW)['admitted'])
            self.assertIn('network=eth',fetch.call_args.args[0])
            self.assertFalse(admission.evaluate(item,now=NOW+60)['admitted'])
    def test_signed_claim_cannot_substitute_router_or_selector(self):
        for mutation in ('router','code','selector'):
            self.bundle=fixture();self.item['admission_bundle']=self.bundle
            leg=self.bundle['payload']['evidence']['execution']['metrics']['quotes'][0]
            if mutation=='router':leg['raw']['transaction']['to']=POOL
            if mutation=='code':leg['router_bytecode']='0x6001'
            if mutation=='selector':leg['raw']['transaction']['data']='0xdeadbeef'
            self.sign();self.assertFalse(self.evaluate()['admitted'])
    def test_signed_pool_label_cannot_replace_actual_pool_transfer_proof(self):
        calls=self.bundle['payload']['evidence']['execution']['metrics']['simulation'][0]['calls']
        for index in (2,5):
            for log in calls[index]['logs']:
                log['topics']=[topic(TARGET) if value==topic(POOL) else value for value in log['topics']]
        self.sign();self.assertFalse(self.evaluate()['admitted'])
