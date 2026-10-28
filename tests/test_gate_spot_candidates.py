"""Synthetic strategy qualification and adversarial near-miss fixtures.

A synthetic BUY is reachable; none of these records represents a real token,
reviewer, live assessment or validated trading performance.
"""
import copy
import datetime as dt
import unittest
from unittest.mock import patch

import gate_spot_candidates as g
from asset_identity import key

NOW = 1800000000
TOKEN = '0x'+'1'*40
IDENTITY = key('eth',TOKEN)


def iso(t): return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()


def review():
    return dict(network='eth',contract=TOKEN,reviewer='SYNTHETIC TEST REVIEWER',reviewed_at=iso(NOW-60),expires_at=iso(NOW+86400),
                sources=[dict(url='https://primary.example/tokenomics',kind='primary',content_sha256='a'*64,reviewed_at=iso(NOW-60),covers=['supply','unlocks','authority']),
                         dict(url='https://independent.example/holders',kind='independent',content_sha256='b'*64,reviewed_at=iso(NOW-60),covers=['holders'])],
                authority_assessment='NO_UNRESOLVED_CRITICAL_CONCERNS',authority_notes='SYNTHETIC authority review with documented limitations',
                holder_exclusion_notes='SYNTHETIC LP and burn exclusion methodology with sources',circulation_methodology='SYNTHETIC reconciliation of circulating and total units',
                unlock_coverage_notes='SYNTHETIC complete disclosure coverage for next 30 days',unlock_coverage_start=iso(NOW-86400),unlock_coverage_end=iso(NOW+40*86400),
                circulating_supply=1000000,total_supply=1200000,max_supply=2000000,adjusted_top10_fraction=0.3,unlock_events=[])


def data():
    pair=dict(id='TEST_USDT',base='TEST',quote='USDT',type='normal',trade_status='tradable',buy_start=0,sell_start=0,
              delisting_time=0,st_tag=False,precision=3,amount_precision=3,
              min_base_amount='0.01',min_quote_amount='1',max_base_amount=None,max_quote_amount=None)
    end=NOW//300*300-300
    bars=[[str(end-(20-i)*300),'100','9.9','10','9.8','9.9','10','true'] for i in range(21)]
    bars[-1]=[str(end),'200','10.1','10.12','9.9','9.95','20','true']
    safe={'is_honeypot':'0','cannot_sell_all':'0','owner_change_balance':'0','hidden_owner':'0','is_blacklisted':'0','is_open_source':'1',
          'is_mintable':'0','trading_cooldown':'0','is_proxy':'0','transfer_pausable':'0','slippage_modifiable':'0','personal_slippage_modifiable':'0','selfdestruct':'0'}
    return dict(pair=pair,currency=dict(currency='TEST',delisted=False,trade_disabled=False,chains=[dict(name='ETH',addr=TOKEN)]),
                chains=[dict(chain='ETH',contract_address=TOKEN,is_disabled=0,is_deposit_disabled=0,is_withdraw_disabled=0)],
                security=dict(code=1,result={TOKEN:safe}),supply=dict(platforms={'ethereum':TOKEN},last_updated=iso(NOW-30),market_data=dict(circulating_supply=1000000,total_supply=1200000,max_supply=2000000)),
                bars=bars,book=dict(current=NOW*1000,update=NOW*1000-1,asks=[['10.11','1000']],bids=[['10.10','1000']]))


def scanner(d=None,r=None):
    d=data() if d is None else d
    r={IDENTITY:review()} if r is None else r
    def fetch(url):
        if 'goplus' in url: return copy.deepcopy(d['security'])
        if 'coingecko' in url:return copy.deepcopy(d['supply'])
        path=url.split('/api/v4')[1].split('?')[0]
        if path=='/spot/currencies':return [copy.deepcopy(d['currency'])]
        if path=='/spot/currency_pairs':return [copy.deepcopy(d['pair'])]
        if path=='/wallet/currency_chains':return copy.deepcopy(d['chains'])
        if path=='/spot/currency_pairs/TEST_USDT':return copy.deepcopy(d['pair'])
        if path=='/spot/candlesticks':return copy.deepcopy(d['bars'])
        if path=='/spot/order_book':return copy.deepcopy(d['book'])
        raise AssertionError('Unexpected request: '+url)
    engine=g.Scanner(fetch,r)
    engine.gate.catalog();engine.gate.catalog_at=NOW
    return engine


class CandidateTests(unittest.TestCase):
    def evaluate(self,d=None,r=None):return scanner(d,r).assess(dict(network='eth',token_address=TOKEN),NOW)
    def assert_blocked(self,d=None,r=None):
        result=self.evaluate(d,r)
        self.assertNotEqual(result['classification'],g.LABEL)
        self.assertIsNone(result['plan'])
        self.assertTrue(result['blockers'])
        return result

    def test_complete_synthetic_case_reaches_manual_candidate_not_execution(self):
        result=self.evaluate()
        self.assertEqual(result['classification'],g.LABEL,result['blockers'])
        self.assertFalse(result['automatic_trading_enabled']);self.assertFalse(result['orders_allowed'])
        p=result['plan'];self.assertLessEqual(p['paper_notional_usdt'],25)
        self.assertLessEqual(p['planned_paper_loss_usdt'],10)
        self.assertEqual(g.stamp(p['expires_at']),NOW+30)
        self.assertGreater(p['take_profit_reference_usdt'],float(p['entry_limit_usdt']))
        text=g.format_alert(result)
        for phrase in ('PAPER STRATEGY','Expires:','Invalidation:','not a prediction','fees/eligibility'):self.assertIn(phrase,text)

    def test_boolean_claims_do_not_replace_review(self):
        self.assert_blocked(r={IDENTITY:{'verified':True,'tokenomics_verified':True}})
        self.assert_blocked(r={})

    def test_expired_future_and_missing_review_coverage_block(self):
        for updates in (dict(expires_at=iso(NOW-1)),dict(reviewed_at=iso(NOW+1)),dict(unlock_coverage_end=iso(NOW+86400)),dict(authority_notes=''),dict(authority_assessment='UNKNOWN')):
            r=review();r.update(updates);self.assert_blocked(r={IDENTITY:r})

    def test_source_identity_digest_and_topic_coverage_required(self):
        for change in ('same_host','no_primary','bad_digest','missing_holders','future_source'):
            r=review()
            if change=='same_host':r['sources'][1]['url']='https://primary.example/mirror'
            if change=='no_primary':r['sources'][0]['kind']='independent'
            if change=='bad_digest':r['sources'][0]['content_sha256']='verified'
            if change=='missing_holders':r['sources'][1]['covers']=[]
            if change=='future_source':r['sources'][0]['reviewed_at']=iso(NOW+1)
            self.assert_blocked(r={IDENTITY:r})

    def test_review_wrong_contract_dilution_concentration_unlock_block(self):
        for updates in (dict(contract='0x'+'2'*40),dict(max_supply=10000000),dict(adjusted_top10_fraction=0.8),dict(unlock_events=[dict(at=iso(NOW+3600),amount=200000)])):
            r=review();r.update(updates);self.assert_blocked(r={IDENTITY:r})

    def test_live_security_adverse_cannot_be_overridden(self):
        d=data();d['security']['result'][TOKEN]['is_honeypot']='1'
        r=self.assert_blocked(d);self.assertEqual(r['classification'],'AVOID / HIGH CONCERN')

    def test_unknown_security_is_not_clear(self):
        d=data();del d['security']['result'][TOKEN]['is_open_source'];self.assert_blocked(d)

    def test_live_supply_stale_conflicting_or_wrong_contract_blocks(self):
        for change in ('stale','wrong_token','conflict','missing','bool'):
            d=data()
            if change=='stale':d['supply']['last_updated']=iso(NOW-3601)
            if change=='wrong_token':d['supply']['platforms']['ethereum']='0x'+'2'*40
            if change=='conflict':d['supply']['market_data']['max_supply']=3000000
            if change=='missing':d['supply']['market_data']['circulating_supply']=None
            if change=='bool':d['supply']['market_data']['total_supply']=True
            self.assert_blocked(d)

    def test_pair_disabled_premarket_wrong_network_block(self):
        for updates in (dict(trade_status='buyable'),dict(type='premarket'),dict(st_tag=True),dict(delisting_time=NOW+60)):
            d=data();d['pair'].update(updates);self.assert_blocked(d)
        d=data();d['chains'][0]['chain']='BASEEVM';self.assert_blocked(d)

    def test_market_stale_wide_thin_crossed_or_slippage_blocks(self):
        for updates in (dict(current=(NOW-31)*1000,update=(NOW-32)*1000),dict(bids=[['9.9','1000']]),dict(asks=[['10.11','1']]),dict(bids=[['10.2','1000']]),dict(current=(NOW+10)*1000)):
            d=data();d['book'].update(updates);self.assert_blocked(d)

    def test_no_breakout_open_duplicate_and_low_volume_candles_block(self):
        for change in ('no_breakout','open','duplicate','volume','gap'):
            d=data()
            if change=='no_breakout':d['bars'][-1][2]='9.99'
            if change=='open':d['bars'][-1][7]='false'
            if change=='duplicate':d['bars'][-1][0]=d['bars'][-2][0]
            if change=='volume':d['bars'][-1][1]='100'
            if change=='gap':d['bars'][-2][0]=str(int(d['bars'][-2][0])-300)
            self.assert_blocked(d)

    def test_limits_precision_extended_entry_and_zero_size_block(self):
        for change in ('min_quote','precision','extension','min_units','zero_units'):
            d=data()
            if change=='min_quote':d['pair']['min_quote_amount']='100'
            if change=='precision':d['pair']['precision']=None
            if change=='extension':d['book']['asks']=[['11','1000']]
            if change=='min_units':d['pair']['min_base_amount']='100'
            if change=='zero_units':d['pair']['amount_precision']=0;d['pair']['precision']=0
            self.assert_blocked(d)

    def test_provider_outage_remains_wait(self):
        engine=scanner()
        engine.fetch=lambda _:(_ for _ in ()).throw(OSError('SECRET'))
        r=engine.assess(dict(network='eth',token_address=TOKEN),NOW)
        self.assertNotEqual(r['classification'],g.LABEL)
        self.assertNotIn('SECRET',str(r))

    def test_empty_real_review_registry_is_explicit(self):
        r=g.run(fetch=lambda _:self.fail('No request needed'),reviews={})
        self.assertEqual(r['candidates'],[]);self.assertIn('No documented',r['errors'][0])

    def test_full_runner_reaches_synthetic_candidate(self):
        engine=scanner()
        with patch('gate_spot_research.dt') as clock:
            clock.datetime.now.return_value.timestamp.return_value=NOW
            clock.timezone=dt.timezone
            r=g.run(fetch=engine.fetch,now=NOW,reviews={IDENTITY:review()})
        self.assertEqual(r['candidates'][0]['classification'],g.LABEL,r)

class PaperTrackingTests(unittest.TestCase):
    def candidate(self):
        result=scanner().assess(dict(network='eth',token_address=TOKEN),NOW)
        self.assertEqual(result['classification'],g.LABEL)
        return result

    def test_confirmed_alert_is_deduplicated_and_never_assumes_fill(self):
        report=dict(candidates=[self.candidate()]);history=dict(version=1,signals={})
        sent=[]
        def send(text):sent.append(text);return True
        updated,events=g.process(report,history,send,NOW)
        again,events2=g.process(report,updated,send,NOW+1)
        self.assertEqual(len(sent),1);self.assertEqual(events[0]['status'],'NOTIFIED')
        self.assertEqual(events2,[]);self.assertEqual(len(again['signals']),1)
        self.assertEqual(next(iter(again['signals'].values()))['position_status'],'NO_ORDER_OR_FILL_ASSUMED')
        self.assertEqual(history['signals'],{})

    def test_failed_delivery_is_retryable_and_does_not_save_receipt(self):
        report=dict(candidates=[self.candidate()]);history=dict(version=1,signals={})
        updated,events=g.process(report,history,lambda _:False,NOW)
        self.assertEqual(updated['signals'],{});self.assertEqual(events[0]['status'],'DELIVERY_FAILED')
        retried,_=g.process(report,updated,lambda _:True,NOW+1)
        self.assertEqual(len(retried['signals']),1)

    def test_expired_signal_is_not_sent(self):
        report=dict(candidates=[self.candidate()])
        updated,events=g.process(report,dict(version=1,signals={}),lambda _:self.fail('Expired alert'),NOW+31)
        self.assertEqual(updated['signals'],{});self.assertEqual(events[0]['status'],'EXPIRED_BEFORE_DELIVERY')

    def test_forward_observation_is_not_profit_and_missing_horizons_stay_missing(self):
        candidate=self.candidate();report=dict(candidates=[candidate])
        history,_=g.process(report,dict(version=1,signals={}),lambda _:True,NOW)
        later=copy.deepcopy(candidate);later['classification']='WAIT / VERIFY';later['plan']=None
        later['evidence']['market']['book'].update(current=(NOW+3600)*1000,update=(NOW+3600)*1000)
        marked,_=g.process(dict(candidates=[later]),history,now=NOW+3600)
        observations=next(iter(marked['signals'].values()))['forward_observations']
        self.assertIn('3600',observations);self.assertNotIn('86400',observations)
        self.assertIn('NOT realized',observations['3600']['meaning'])

    def test_corrupt_state_is_rejected(self):
        with self.assertRaises(ValueError):g.process(dict(candidates=[]),dict(version=2,signals={}))

class LiveSchemaTests(unittest.TestCase):
    def test_omitted_optional_maximum_is_disclosed_not_false_zero(self):
        d=data();del d['pair']['max_base_amount']
        r=scanner(d).assess(dict(network='eth',token_address=TOKEN),NOW)
        self.assertEqual(r['classification'],g.LABEL,r['blockers'])
        self.assertIn('max_base_amount',r['plan']['unexposed_maximum_limits'])
    def test_missing_minimum_still_blocks(self):
        d=data();del d['pair']['min_quote_amount']
        r=scanner(d).assess(dict(network='eth',token_address=TOKEN),NOW)
        self.assertNotEqual(r['classification'],g.LABEL)
