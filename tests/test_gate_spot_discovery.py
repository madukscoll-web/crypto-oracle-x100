import copy
import unittest
from unittest.mock import patch
import gate_spot_discovery as d
from test_gate_spot_candidates import data,scanner,NOW,TOKEN


def universe(count=3):
    currencies=[];pairs=[];tickers=[]
    for i in range(count):
        symbol='T'+str(i);addr='0x'+format(i+1,'040x')
        currencies.append(dict(currency=symbol,delisted=False,trade_disabled=False,chains=[dict(name='ETH',addr=addr)]))
        pairs.append(dict(id=symbol+'_USDT',base=symbol,quote='USDT',type='normal',trade_status='tradable',st_tag=False,delisting_time=0,buy_start=NOW-60 if i==0 else NOW-40*86400,sell_start=NOW-60 if i==0 else NOW-40*86400))
        tickers.append(dict(currency_pair=symbol+'_USDT',quote_volume=str(1000000+i*100000),last='10',lowest_ask='10.01',highest_bid='10'))
    return currencies,pairs,tickers


class DiscoveryTests(unittest.TestCase):
    def test_recent_priority_and_bounded_selection(self):
        selected,coverage=d.select(*universe(10),NOW,4)
        self.assertEqual(len(selected),4);self.assertEqual(selected[0]['symbol'],'T0')
        self.assertEqual(coverage['prefilter_eligible'],10);self.assertEqual(len(coverage['unexamined_eligible_pairs']),6)
        self.assertIn('not token age',selected[0]['listing_time_semantics'])

    def test_exact_contract_required_not_ticker_alone(self):
        c,p,t=universe();c[0]['chains'][0]['addr']=''
        selected,_=d.select(c,p,t,NOW)
        self.assertNotIn('T0',[x['symbol']for x in selected])

    def test_disabled_st_premarket_and_activation_unknown_excluded(self):
        for updates in (dict(st_tag=True),dict(type='premarket'),dict(trade_status='buyable'),dict(buy_start=None),dict(sell_start=NOW+1),dict(delisting_time=NOW+3600)):
            c,p,t=universe();p[0].update(updates)
            selected,_=d.select(c,p,t,NOW)
            self.assertNotIn('T0',[x['symbol']for x in selected])

    def test_malformed_nonfinite_thin_crossed_or_leveraged_tickers_excluded(self):
        for updates in (dict(quote_volume='NaN'),dict(quote_volume=True),dict(quote_volume='10'),dict(highest_bid='11'),dict(etf_leverage='3'),dict(lowest_ask='12')):
            c,p,t=universe();t[0].update(updates)
            selected,_=d.select(c,p,t,NOW)
            self.assertNotIn('T0',[x['symbol']for x in selected])

    def test_duplicate_metadata_does_not_select_an_ambiguous_join(self):
        c,p,t=universe();t.append(copy.deepcopy(t[0]))
        selected,_=d.select(c,p,t,NOW)
        self.assertNotIn('T0',[x['symbol']for x in selected])
        with self.assertRaises(ValueError):d.select(c,p,t,NOW,31)

    def test_supported_chain_representation_is_explicit(self):
        c,p,t=universe();c[0]['chains']=[dict(name='BASEEVM',addr=TOKEN),dict(name='ETH',addr='0x'+'2'*40)]
        selected,_=d.select(c,p,t,NOW)
        first=next(x for x in selected if x['symbol']=='T0')
        self.assertEqual(first['network'],'eth');self.assertEqual(first['representation_count'],2)
        self.assertEqual(first['token_address'],'0x'+'2'*40)

    def test_empty_and_failed_catalog_never_claim_market_absence_or_buy(self):
        def failed(_):raise OSError('PRIVATE')
        result=d.run(failed)
        self.assertEqual(result['counts']['buy_candidates'],0)
        self.assertTrue(result['errors']);self.assertNotIn('PRIVATE',str(result))
        self.assertFalse(result['buy_authorized'])

    def test_complete_market_setup_is_still_not_buy_without_review(self):
        engine=scanner();asset=dict(symbol='TEST',network='eth',token_address=TOKEN,asset_key='eip155:1:'+TOKEN,pair_id='TEST_USDT')
        # Freeze the pure strategy clock through its explicit argument by patching
        # the strategy call, without treating that as complete investment evidence.
        eligibility=engine.gate.eligibility(asset,NOW)
        with patch.object(engine.gate,'eligibility',return_value=eligibility), patch.object(d,'strategy',return_value={'fixture_only':True}):
            result=d.assess(engine.gate,asset,engine.fetch)
        self.assertFalse(result['buy_authorized'])
        self.assertNotIn('BUY CANDIDATE',result['classification'])
        self.assertTrue(any('review not completed'in x for x in result['blockers']))

class DiscoveryScopeTests(unittest.TestCase):
    def test_native_representations_and_issuer_categories_do_not_enter_utility_cohort(self):
        c,p,t=universe();c[0]['category']=['stocks']
        selected,coverage=d.select(c,p,t,NOW)
        self.assertNotIn('T0',[x['symbol']for x in selected])
        for code in ('BTC','ETH','BNB','SOL'):
            c,p,t=universe(1);c[0]['currency']=code;p[0].update(base=code,id=code+'_USDT');t[0]['currency_pair']=code+'_USDT'
            self.assertEqual(d.select(c,p,t,NOW)[0],[])

    def test_supplied_interval_cannot_shorten_default_or_overrun_time_budget(self):
        from provider_session import Session,ProviderUnavailable
        now=[0];waits=[]
        def sleep(t):waits.append(t);now[0]+=t
        session=Session(max_seconds=20,clock=lambda:now[0],sleeper=sleep,transport=lambda *args:{},host_intervals={'api.coingecko.com':8})
        session.get('https://api.coingecko.com/a');session.get('https://api.coingecko.com/b')
        self.assertEqual(waits,[8]);now[0]=15
        session.last['api.coingecko.com']=15
        with self.assertRaises(ProviderUnavailable):session.get('https://api.coingecko.com/c')
        self.assertEqual(waits,[8])
        with self.assertRaises(ValueError):Session(host_intervals={'api.coingecko.com':float('nan')})
