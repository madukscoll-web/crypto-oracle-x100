import datetime as dt
import unittest
from unlock_provider import collect
A='0x'+'a'*40
NOW=int(dt.datetime(2026,10,21,tzinfo=dt.timezone.utc).timestamp())
def stamp(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()
REGISTRY=dict(provider_bindings={'eth:'+A:dict(tokenomist_id='fixture',source_url='https://issuer.example/contracts',observed_at=stamp(NOW))})
ENV=dict(TOKENOMIST_API_KEY='secret-fixture')
class UnlockProviderTests(unittest.TestCase):
    def transport(self,variant=None):
        def provider(url,key):
            meta=dict(queryDate=stamp(NOW),credit=dict(used=123))
            if '/token/list' in url:return dict(status=True,metadata=meta,data=[dict(id='fixture')])
            if '/allocations/' in url:return dict(status=True,metadata=meta,data=dict(totalTBDLockedAmount=10,totalUntrackedAmount=5))
            meta.update(page=1,totalPages=1,total=1)
            data=[dict(startDate=stamp(NOW),endDate=stamp(NOW+86400),unlockAmount=100)]
            if variant=='empty':data=[];meta['total']=0
            if variant=='partial':meta['totalPages']=5;meta['total']=500
            if variant=='invalid_page':meta['page']=False
            return dict(status=True,metadata=meta,data=data)
        return provider
    def test_authenticated_disclosures_are_not_verified_complete_supply(self):
        result=collect(dict(network='eth',token_address=A),REGISTRY,ENV,self.transport(),NOW)
        self.assertEqual(result['status'],'LIMITED')
        self.assertEqual(result['metrics']['tbd_locked_tokens'],'10')
        self.assertFalse(result['metrics']['complete_future_coverage_verified'])
        self.assertFalse(result['metrics']['independent_contract_binding_verified'])
        self.assertNotIn('secret-fixture',str(result));self.assertNotIn('credit',str(result))
    def test_missing_credential_or_binding_never_calls_api(self):
        def forbidden(*args):self.fail('Unexpected API call')
        self.assertEqual(collect(dict(network='eth',token_address=A),REGISTRY,{},forbidden,NOW)['status'],'UNKNOWN')
        self.assertEqual(collect(dict(network='eth',token_address=A),{},ENV,forbidden,NOW)['status'],'UNKNOWN')
    def test_empty_calendar_and_invalid_pagination_are_unknown(self):
        for case in ('empty','partial','invalid_page'):
            result=collect(dict(network='eth',token_address=A),REGISTRY,ENV,self.transport(case),NOW)
            self.assertEqual(result['status'],'UNKNOWN')
