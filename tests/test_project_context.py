import copy
import datetime as dt
import json
import unittest

import fundamental_evidence
import project_context as context
import technical_watch
from test_technical_watch import fixture as watch_fixture, NOW as WATCH_NOW


NOW = dt.datetime(2026,11,5,7,tzinfo=dt.timezone.utc).timestamp()
TOKEN = '0x'+'a'*40


def payload(coin='avalanche-2',symbol='avax'):
    return dict(id=coin,symbol=symbol,name='Fixture project',platforms={'ethereum':TOKEN},
        description={'en':'<p>Provides a network for applications.</p>'},
        links={'homepage':['https://project.example'], 'repos_url':{'github':['https://github.com/example/project']}},
        developer_data={'commit_count_4_weeks':25,'pull_requests_merged':12},
        community_data={'twitter_followers':10000,'telegram_channel_user_count':None},
        market_data={'circulating_supply':100,'total_supply':150,'max_supply':200,
                     'market_cap':{'usd':1000},'fully_diluted_valuation':{'usd':2000}},
        last_updated=context.iso(NOW), categories=['Layer 1'])


def currency(symbol='AVAX',token=False):
    return dict(currency=symbol,delisted=False,trade_disabled=False,
                chains=[{'name':'ETH','addr':TOKEN}] if token else [])


def cache(): return {'version':1,'entries':{}}


class ContextTests(unittest.TestCase):
    def test_all_book_topics_have_explicit_unknowns_and_no_approval(self):
        p=context.empty({'network':'eth','token_address':TOKEN},NOW)
        self.assertEqual(set(p['dimensions']),set(context.DIMENSIONS))
        self.assertTrue(all(d['status']=='UNKNOWN' and d['value'] is None for d in p['dimensions'].values()))
        self.assertFalse(p['buy_authorized']);self.assertFalse(p['orders_allowed'])
        self.assertIn('blockchain',p['questions']['purpose'])

    def test_provider_claims_are_not_adoption_revenue_or_team_verification(self):
        raw=payload();raw['description']['en']='Trusted by 1 million users and backed by famous investors.'
        raw['team']=['Invented CEO'];raw['revenue']=9999999
        p=context.from_payload(raw,{},'https://api.coingecko.com/fixture',NOW)
        self.assertEqual(p['dimensions']['purpose']['status'],'PROVIDER_REPORTED_UNVERIFIED')
        for name in ('adoption','funding','team','distribution','token_value_capture'):
            self.assertIsNone(p['dimensions'][name]['value'])
        self.assertEqual(len(p['sources'][0]['response_sha256']),64)

    def test_developer_and_community_counts_are_not_quality_or_organic_proof(self):
        p=context.from_payload(payload(),{},'https://api.coingecko.com/fixture',NOW)
        self.assertEqual(p['dimensions']['development']['value']['commit_count_4_weeks'],25)
        self.assertEqual(p['dimensions']['community']['value']['twitter_followers'],10000)
        self.assertEqual(p['dimensions']['community']['value']['organic_activity_retention_and_bot_filtering'],'UNKNOWN')

    def test_missing_supply_stays_unknown_and_zero_is_not_turned_into_missing(self):
        raw=payload();raw['market_data'].update(circulating_supply=0,max_supply=None)
        raw['community_data']['twitter_followers']=0
        p=context.from_payload(raw,{},'https://api.coingecko.com/fixture',NOW)
        self.assertIsNone(p['dimensions']['supply']['value']['max_supply'])
        self.assertEqual(p['dimensions']['supply']['value']['circulating_supply'],0)
        self.assertEqual(p['dimensions']['community']['value']['twitter_followers'],0)
        self.assertEqual(p['dimensions']['supply']['value']['unlocks_30d'],'UNKNOWN')

    def test_supply_conflicts_and_stale_market_observations_are_labelled(self):
        raw=payload();raw['market_data']['circulating_supply']=300
        p=context.from_payload(raw,{},'https://api.coingecko.com/fixture',NOW)
        self.assertEqual(p['dimensions']['supply']['status'],'CONFLICTING')
        raw=payload();raw['last_updated']='2020-01-01T00:00:00Z'
        p=context.from_payload(raw,{},'https://api.coingecko.com/fixture',NOW)
        self.assertEqual(p['dimensions']['supply']['status'],'STALE_OR_FUTURE_PROVIDER_DATA')

    def test_exact_contract_mismatch_does_not_attach_same_ticker_facts(self):
        item={'network':'eth','token_address':'0x'+'b'*40}
        p=context.exact_contract(item,payload(),'https://api.coingecko.com/fixture',NOW)
        self.assertEqual(p['status'],'IDENTITY_UNRESOLVED')
        self.assertIsNone(p['dimensions']['purpose']['value'])

    def test_native_gate_identity_is_curated_and_never_onchain_verification(self):
        p=context.for_gate('AVAX_USDT',currency(),lambda _:payload(),cache(),NOW)
        self.assertEqual(p['identity']['identity_status'],'CURATED_ASSOCIATION_UNVERIFIED')
        self.assertIn('PRIMARY_DOCUMENTATION',p['dimensions']['purpose']['status'])
        self.assertIsNone(p['dimensions']['adoption']['value'])
        self.assertFalse(p['buy_authorized'])

    def test_wrong_provider_id_or_symbol_suppresses_all_provider_facts(self):
        for raw in (payload(coin='fake-avax'),payload(symbol='wrong')):
            p=context.for_gate('AVAX_USDT',currency(),lambda _:raw,cache(),NOW)
            self.assertEqual(p['status'],'IDENTITY_UNRESOLVED')
            self.assertIsNone(p['dimensions']['purpose']['value'])

    def test_gate_tokens_require_matching_contract_not_only_symbol(self):
        raw=payload('aave','aave');raw['platforms']['ethereum']='0x'+'b'*40
        p=context.for_gate('AAVE_USDT',currency('AAVE',True),lambda _:raw,cache(),NOW)
        self.assertEqual(p['status'],'IDENTITY_UNRESOLVED')
        p=context.for_gate('AAVE_USDT',currency('AAVE',True),lambda _:payload('aave','aave'),cache(),NOW)
        self.assertEqual(p['dimensions']['purpose']['status'],'PROVIDER_REPORTED_UNVERIFIED')

    def test_unknown_gate_coin_does_not_search_by_ticker(self):
        def forbidden(_): self.fail('Unknown asset must not be looked up by symbol')
        p=context.for_gate('FAKE_USDT',currency('FAKE'),forbidden,cache(),NOW)
        self.assertTrue(all(d['value'] is None for d in p['dimensions'].values()))

    def test_outage_preserves_documented_native_mechanism_but_not_fake_metrics(self):
        def outage(_):raise OSError('fixture outage')
        p=context.for_gate('NEAR_USDT',currency('NEAR'),outage,cache(),NOW)
        self.assertIn('NEAR',p['dimensions']['purpose']['value'])
        self.assertIsNone(p['dimensions']['supply']['value'])
        self.assertIsNone(p['dimensions']['funding']['value'])

    def test_cache_reuses_original_observation_and_contract_changes_invalidate_it(self):
        c=cache();calls=[]
        def fetch(url):calls.append(url);return payload('aave','aave')
        first=context.for_gate('AAVE_USDT',currency('AAVE',True),fetch,c,NOW)
        later=context.for_gate('AAVE_USDT',currency('AAVE',True),fetch,c,NOW+3600)
        self.assertEqual(len(calls),1)
        self.assertEqual(first['retrieved_at'],later['retrieved_at'])
        changed=currency('AAVE',True);changed['chains'][0]['addr']='0x'+'b'*40
        context.for_gate('AAVE_USDT',changed,fetch,c,NOW+3601)
        self.assertEqual(len(calls),2)

    def test_dex_reuses_existing_response_without_extra_provider_calls(self):
        calls=[];item=dict(network='eth',token_address=TOKEN)
        def fetch(url):calls.append(url);return payload('aave','aave')
        fundamental_evidence.collect(item,fetch,dt.datetime.fromtimestamp(NOW,dt.timezone.utc))
        self.assertEqual(len(calls),1)
        self.assertEqual(item['project_context']['dimensions']['purpose']['status'],'PROVIDER_REPORTED_UNVERIFIED')

    def test_all_gate_timeframes_receive_context_with_one_fetch_per_asset(self):
        report={'results':[{'pair':'AVAX_USDT','interval':'1d'},{'pair':'AVAX_USDT','interval':'1w'}]}
        calls=[]
        def fetch(url):
            calls.append(url)
            return [currency()] if url.endswith('/spot/currencies') else payload()
        context.attach_gate(report,fetch,cache(),NOW)
        self.assertEqual(len(calls),2)
        self.assertTrue(all('project_context' in row for row in report['results']))
        self.assertEqual(report['project_context_coverage']['independently_verified'],0)

    def test_html_controls_links_and_large_summaries_do_not_hide_disclosures(self):
        self.assertEqual(context.clean('<script>BUY</script><b>Utility</b>\u202e\ntext'),'Utility text')
        for url in ('http://insecure.example','https://127.0.0.1','https://x:y@evil.example','https://x.internal'):
            self.assertIsNone(context.safe_url(url))
        p=context.from_payload(payload(),{},'https://api.coingecko.com/'+'x'*450,NOW)
        text=context.summary(p)
        self.assertLessEqual(len(text.encode('utf-16-le'))//2,1350)
        self.assertIn('UNKNOWN',text);self.assertIn('not approval',text)

    def test_technical_message_attachment_preserves_buy_warning_and_size(self):
        report,fetch=watch_fixture()
        row=report['results'][0]
        row['project_context']=context.for_gate('AVAX_USDT',currency(),lambda _:payload(),cache(),NOW)
        screened=technical_watch.screen(row,row['research'],technical_watch.PublicGate(fetch),
                     [dict(currency='BCH',delisted=False,trade_disabled=False,chains=[])],set(),lambda:WATCH_NOW)
        message=technical_watch.message(row,row['research'],screened)
        self.assertIn('PROJECT FUNDAMENTALS',message)
        self.assertIn('NOT APPROVED FOR PURCHASE',message)
        self.assertLessEqual(len(message.encode('utf-16-le'))//2,3900)

    def test_wrong_market_profile_is_not_rendered_for_another_coin(self):
        p=context.for_gate('AVAX_USDT',currency(),lambda _:payload(),cache(),NOW)
        text=context.summary(p,expected={'pair':'BCH_USDT'})
        self.assertIn('Use/value: UNKNOWN',text)
        self.assertNotIn('Avalanche network utility',text)

    def test_cached_supply_is_marked_stale_when_source_age_crosses_a_day(self):
        raw=payload();raw['last_updated']=context.iso(NOW-80000)
        c=cache()
        context.for_gate('AVAX_USDT',currency(),lambda _:raw,c,NOW)
        p=context.for_gate('AVAX_USDT',currency(),lambda _:self.fail('Should reuse metadata cache'),c,NOW+10000)
        self.assertEqual(p['dimensions']['supply']['status'],'STALE_OR_FUTURE_PROVIDER_DATA')

    def test_unavailable_provider_retries_after_short_negative_cache(self):
        c=cache()
        def outage(_):raise OSError()
        context.for_gate('AVAX_USDT',currency(),outage,c,NOW)
        p=context.for_gate('AVAX_USDT',currency(),lambda _:payload(),c,NOW+901)
        self.assertEqual(p['dimensions']['supply']['status'],'PROVIDER_REPORTED_UNVERIFIED')

    def test_cache_cannot_introduce_a_verified_fundamentals_label(self):
        c=cache()
        context.for_gate('AVAX_USDT',currency(),lambda _:payload(),c,NOW)
        entry=next(iter(c['entries'].values()))
        entry['profile']['dimensions']['team']={'status':'VERIFIED','value':'Fake founder'}
        p=context.for_gate('AVAX_USDT',currency(),lambda _:payload(),c,NOW+1)
        self.assertEqual(p['dimensions']['team']['status'],'UNKNOWN')
        self.assertIsNone(p['dimensions']['team']['value'])
