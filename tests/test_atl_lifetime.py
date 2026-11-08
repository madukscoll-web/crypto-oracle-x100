"""Synthetic independently signed source fixtures; never production enrollment."""
import base64
import copy
import datetime as dt
import hashlib
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import authenticated_admission as auth
import atl_lifetime as atl

NOW=1800000000
TOKEN='0x'+'1'*40
ASSET={'network':'eth','contract':TOKEN}
def at(x):return dt.datetime.fromtimestamp(x,dt.timezone.utc).isoformat()


class LifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory();cls.path=pathlib.Path(cls.folder.name);cls.trust={'schema':auth.VERSION,'reviewers':{},'sources':{}}
        for n in ('one','two'):
            key=cls.path/n
            subprocess.run(['openssl','genpkey','-algorithm','Ed25519','-out',str(key)],check=True,capture_output=True)
            public=subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],check=True,capture_output=True).stdout.decode()
            cls.trust['reviewers'][n]=dict(public_key=public,organization=n,revoked=False,valid_from=at(NOW-100),valid_until=at(NOW+1000),scopes=['atl_lifetime'])
    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()
    def setUp(self):
        self.registry=dict(schema=atl.SCHEMA,sources={n:dict(repository=n+'/history',path_prefix='atl/',organization='source-'+n) for n in ('one','two')},manifests={})
        self.raw={};self.bundle={'payload':dict(schema=atl.SCHEMA,identity=ASSET,observed_at=at(NOW),expires_at=at(NOW+100),first_trade_at=at(NOW-180),
            venues=['fixture_venue'],first_candle_scope='POST_LISTING_TRADES_ONLY',transformations=[],instrument='ORDINARY_CRYPTO',security_review=dict(verdict='VERIFIED_RESEARCH_ONLY',identity=ASSET,observed_at=at(NOW),expires_at=at(NOW+100),
                controls={k:'VERIFIED' for k in ('identity','sellability','taxes','authority','lp_controls','holders','circulation','vesting','bridge_backing')}),archives=[]),'signatures':[]}
        for n in ('one','two'):
            raw=dict(schema='atl-minute-archive-v1',source_id=n,identity=ASSET,quote='USD_PER_WHOLE_TOKEN',observed_at=at(NOW),transformations=[],
                market=dict(price_usd='1',circulating_supply='200000000',circulating_market_cap_usd='200000000',observed_at=at(NOW)),
                venues={'fixture_venue':[[NOW-180,1.1,1.2,1,1.1,10],[NOW-120,1.1,1.2,1,1.1,10],[NOW-60,1.1,1.2,1,1,10]]})
            ref=dict(source=n,commit='a'*40,path='atl/fixture.json',sha256=hashlib.sha256(auth.canonical(raw)).hexdigest())
            self.bundle['payload']['archives'].append(ref);self.raw[n]=raw
        self.p1=patch.object(atl,'load_registry',return_value=self.registry);self.p2=patch.object(auth,'load_trust',return_value=copy.deepcopy(self.trust))
        self.p1.start();self.p2.start();self.addCleanup(self.p1.stop);self.addCleanup(self.p2.stop)
        self.fetches=[]
    def sign(self):
        for ref in self.bundle['payload']['archives']:ref['sha256']=hashlib.sha256(auth.canonical(self.raw[ref['source']])).hexdigest()
        file=self.path/'message';file.write_bytes(auth.canonical(self.bundle['payload']))
        self.bundle['signatures']=[]
        for n in ('one','two'):
            signature=subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.path/n),'-rawin','-in',str(file)],check=True,capture_output=True).stdout
            self.bundle['signatures'].append({'reviewer':n,'signature':base64.b64encode(signature).decode()})
    def fetch(self,url):
        self.fetches.append(url)
        for n in ('one','two'):
            if url.startswith('https://raw.githubusercontent.com/'+n+'/history/'):return copy.deepcopy(self.raw[n])
        raise AssertionError('Unapproved URL')
    def evaluate(self):return atl.evaluate(self.bundle,ASSET,self.fetch,now=NOW)
    def test_genuine_signed_synthetic_complete_lifetime_can_qualify_research(self):
        self.sign();result=self.evaluate()
        self.assertTrue(result['lifetime_verified'],result)
        self.assertEqual(result['classification'],'ALL TIME LOW')
        self.assertFalse(result['buy_authorized']);self.assertFalse(result['orders_allowed'])
        self.assertEqual(len(self.fetches),2)
    def test_unsigned_flags_and_mutated_signed_evidence_fail(self):
        self.bundle['payload']['lifetime_complete']=True
        self.assertFalse(self.evaluate()['lifetime_verified'])
        self.sign();self.raw['one']['market']['price_usd']='100'
        self.assertFalse(self.evaluate()['lifetime_verified'])
    def test_missing_minute_duplicate_identity_or_cap_conflict_fail(self):
        for mutate in ('gap','duplicate','identity','cap','supply'):
            with self.subTest(mutate=mutate):
                raw=copy.deepcopy(self.raw['one'])
                if mutate=='gap':self.raw['one']['venues']['fixture_venue'].pop()
                elif mutate=='duplicate':self.raw['one']['venues']['fixture_venue'][1][0]=NOW-180
                elif mutate=='identity':self.raw['one']['identity']={'network':'bsc','contract':TOKEN}
                elif mutate=='cap':self.raw['one']['market']['circulating_market_cap_usd']='1'
                else:self.raw['one']['market']['circulating_supply']='1'
                self.sign();self.assertFalse(self.evaluate()['lifetime_verified']);self.raw['one']=raw
    def test_unknown_migrations_and_security_adverse_never_certify(self):
        self.bundle['payload']['transformations']=[{'split':1000}];self.sign();self.assertFalse(self.evaluate()['lifetime_verified'])
        self.bundle['payload']['transformations']=[]
        self.bundle['payload']['security_review']['controls']['sellability']='NOT_APPLICABLE'
        self.sign();self.assertFalse(self.evaluate()['lifetime_verified'])
    def test_arbitrary_url_path_or_source_is_never_fetched(self):
        for path in ('../../secret.json','http://127.0.0.1/x.json','atl/fixture.json?redirect=x'):
            self.bundle['payload']['archives'][0]['path']=path;self.sign();self.fetches=[]
            self.assertFalse(self.evaluate()['lifetime_verified']);self.assertFalse(self.fetches)
    def test_expired_reviewer_or_same_organization_fails(self):
        self.sign()
        for mutation in ('expired','same_org'):
            trust=copy.deepcopy(self.trust)
            if mutation=='expired':trust['reviewers']['one']['valid_until']=at(NOW)
            else:trust['reviewers']['two']['organization']='one'
            with patch.object(auth,'load_trust',return_value=trust):self.assertFalse(self.evaluate()['lifetime_verified'])
    def test_same_source_family_and_missing_venue_are_rejected(self):
        self.registry['sources']['one']['organization']='coingecko';self.registry['sources']['two']['organization']='geckoterminal'
        self.sign();self.assertFalse(self.evaluate()['lifetime_verified'])
        self.registry['sources']['two']['organization']='independent'
        self.bundle['payload']['venues'].append('uncovered_venue');self.sign()
        self.assertFalse(self.evaluate()['lifetime_verified'])
    def test_near_low_and_no_event_use_replayed_prices(self):
        for n in self.raw:self.raw[n]['market'].update(price_usd='1.04',circulating_market_cap_usd='208000000')
        self.sign();self.assertEqual(self.evaluate()['classification'],'NEAR ALL TIME LOW')
        for n in self.raw:self.raw[n]['market'].update(price_usd='1.50',circulating_market_cap_usd='300000000')
        self.sign();self.assertEqual(self.evaluate()['status'],'VERIFIED_NO_EVENT')
    def test_recovery_requires_recomputed_independent_volume_and_structure(self):
        self.bundle['payload']['first_trade_at']=at(NOW-30*3600)
        self.bundle['payload']['recovery_venue']='fixture_venue'
        for name,raw in self.raw.items():
            rows=[]
            for i in range(30*60):
                hour=i//60;low=9 if hour<20 else 9.4 if hour<25 else 9.5
                close=10.5 if hour==29 else 10
                rows.append([NOW-30*3600+i*60,10,11,low,close,200 if hour==29 else 100])
            raw['venues']['fixture_venue']=rows
            raw['market'].update(price_usd='10.5',circulating_market_cap_usd='2100000000')
        self.sign();self.assertEqual(self.evaluate()['classification'],'ATL RECOVERY WATCH')
        for row in self.raw['two']['venues']['fixture_venue'][-60:]:row[-1]=100
        self.sign();self.assertEqual(self.evaluate()['status'],'VERIFIED_NO_EVENT')

    def test_empty_registry_collect_does_not_fetch_or_invent_proof(self):
        with patch.object(atl,'load_registry',return_value={'schema':atl.SCHEMA,'sources':{},'manifests':{}}):
            summary,notice=atl.collect([{'asset':{'contracts':[ASSET]}}],now=NOW)
        self.assertEqual(summary['status'],'NO_ENROLLED_LIFETIME_EVIDENCE')
        self.assertIsNone(notice)

    def test_coarse_ohlc_and_per_venue_inception_are_supported_without_coverage_gaps(self):
        start=NOW//86400*86400-3*86400;end=NOW//86400*86400
        self.bundle['payload'].update(first_trade_at=at(start+17),venue_first_trade_at={'fixture_venue':at(start+17)})
        for raw in self.raw.values():
            raw['interval_seconds']=86400
            raw['venues']['fixture_venue']=[[t,1.1,1.2,1,1.1,10] for t in range(start,end,86400)]
            raw['partial_candles']={'fixture_venue':[end,1.1,1.2,1,1,10]}
        self.sign();self.assertTrue(self.evaluate()['lifetime_verified'])
        self.raw['one'].pop('partial_candles');self.sign()
        self.assertFalse(self.evaluate()['lifetime_verified'])

    def test_explicit_scope_and_duplicate_archive_controls(self):
        self.sign();trust=copy.deepcopy(self.trust);trust['reviewers']['one']['scopes']='not_atl_lifetime'
        with patch.object(auth,'load_trust',return_value=trust):self.assertFalse(self.evaluate()['lifetime_verified'])
        self.bundle['payload']['archives'][1]=copy.deepcopy(self.bundle['payload']['archives'][0]);self.sign()
        self.assertFalse(self.evaluate()['lifetime_verified'])

    def test_collect_vetoes_asset_type_and_live_cap_conflict(self):
        self.sign();self.registry['manifests']['eth:'+TOKEN]=self.bundle
        d=dict(asset={'contracts':[ASSET]},instrument={'status':'EXCLUDED'},history={'conflicting':False},observed_at=at(NOW),price_usd='1',circulating_market_cap_usd='200000000')
        with patch.object(atl,'fetch_archive',side_effect=self.fetch),patch('research_notice.LABELS',{'ALL TIME LOW','NEAR ALL TIME LOW','ATL RECOVERY WATCH'}):
            result,notice=atl.collect([d],now=NOW)
            self.assertEqual(result['assessed'],1);self.assertFalse(result['findings'][0]['lifetime_verified']);self.assertIsNone(notice)
            d['instrument']['status']='ORDINARY_CRYPTO_RESEARCH';d['circulating_market_cap_usd']='999999999'
            result,notice=atl.collect([d],now=NOW)
            self.assertFalse(result['findings'][0]['lifetime_verified']);self.assertIsNone(notice)
            d['circulating_market_cap_usd']='200000000'
            result,notice=atl.collect([d],now=NOW)
            self.assertEqual(str(notice).splitlines()[:2],['ALL-TIME LOW WATCH','Research subtype: ALL TIME LOW'])
            self.assertIn('NOT A BUY APPROVAL',str(notice))

    def test_qualified_delivery_records_only_exact_receipts_and_deduplicates(self):
        self.sign();self.registry['manifests']['eth:'+TOKEN]=self.bundle
        d=dict(asset={'contracts':[ASSET]},instrument={'status':'ORDINARY_CRYPTO_RESEARCH'},history={'conflicting':False},observed_at=at(NOW),price_usd='1',circulating_market_cap_usd='200000000')
        state={};sent=[];env={'TELEGRAM_BOT_TOKEN':'fixture','TELEGRAM_CHAT_ID':'42'}
        def transport(token,method,data):
            if method=='getChat':return {'ok':True,'result':{'id':42}}
            sent.append(data['text']);return {'ok':True,'result':{'message_id':8,'chat':{'id':42}}}
        with patch.object(atl,'fetch_archive',side_effect=self.fetch),patch('research_notice.LABELS',{'ALL TIME LOW','NEAR ALL TIME LOW','ATL RECOVERY WATCH'}):
            result=atl.deliver([d],state,env,transport,now=NOW)
            self.assertEqual(result['message_id'],8);self.assertEqual(result['delivered'],1)
            saved=next(iter(state['qualified_confirmed'].values()))
            self.assertEqual(saved['message_id'],8);self.assertIn('evidence_sha256',saved)
            result=atl.deliver([d],state,env,transport,now=NOW)
            self.assertEqual(result['delivery_status'],'DAILY_DEDUP');self.assertEqual(len(sent),1)
            state={}
            def bad(token,method,data):
                if method=='getChat':return {'ok':True,'result':{'id':42}}
                return {'ok':True,'result':{'message_id':True,'chat':{'id':42}}}
            result=atl.deliver([d],state,env,bad,now=NOW)
            self.assertEqual(result['failed'],1);self.assertEqual(state,{})

    def test_serialized_result_cannot_mint_notice(self):
        with self.assertRaises(ValueError):atl.notice({'classification':'ALL TIME LOW','lifetime_verified':True})

if __name__=='__main__':unittest.main()
