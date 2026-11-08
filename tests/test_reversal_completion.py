"""Reversal production integration and lifecycle regression, no live messages."""
import copy
import datetime as dt
import unittest
from urllib.parse import parse_qs, urlsplit
from altcoin_reversal_cli import run
from altcoin_reversal_gate import gate_candles
from altcoin_reversal_research import analyze
from reversal_universe import collect
import technical_followup as followup
import technical_watch
import strategy_lab

NOW = 1800000000
PERIODS = {'1h':3600, '4h':14400, '1d':86400, '7d':604800}
PAIR = 'BCH_USDT'


def iso(t):
    return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()


def source_factory(volume=1600):
    calls=[]
    prices=[150-i for i in range(45)]+[120-2*i for i in range(20)]+[80+.65*i for i in range(35)]
    def fetch(url):
        calls.append(url)
        path=urlsplit(url).path
        if path.endswith('/spot/currency_pairs'):
            return [dict(id=PAIR,base='BCH',quote='USDT',type='normal',trade_status='tradable',st_tag=False,buy_start=1,sell_start=1)]
        if path.endswith('/spot/tickers'):
            return [dict(currency_pair=PAIR,quote_volume='2000000')]
        if '/spot/currency_pairs/' in path:
            return dict(id=PAIR,base='BCH',quote='USDT',type='normal',trade_status='tradable',st_tag=False,buy_start=1,sell_start=1)
        if path.endswith('/spot/candlesticks'):
            period=PERIODS[parse_qs(urlsplit(url).query)['interval'][0]]
            return [[str(NOW-(100-i)*period),str(volume if i==99 else 1000),str(p),str(p+1),str(p-1),str(p)] for i,p in enumerate(prices)]
        raise AssertionError(url)
    return fetch,calls


class ReversalCompletionTests(unittest.TestCase):
    def test_intraday_adapter_and_closed_candle_boundary(self):
        for interval in ('1h','4h'):
            fetch,_=source_factory()
            report=run([PAIR],interval,fetch=fetch,now=NOW)
            row=report['results'][0]
            self.assertEqual(row['status'],'RESEARCH_ONLY')
            self.assertEqual(row['research']['interval'],interval)
            self.assertFalse(row['research']['buy_authorized'])
            seconds=PERIODS[interval]
            raw=[[str(NOW-(59-i)*seconds),'1000','100','101','99','100'] for i in range(60)]
            bars=gate_candles(raw,interval_seconds=seconds,now=NOW)
            self.assertEqual(len(bars),59)
            self.assertEqual(bars[-1]['timestamp']+seconds,NOW)

    def test_four_timeframes_reuse_metadata_without_changing_budget_scope(self):
        fetch,calls=source_factory()
        report=collect(fetch=fetch,now=NOW,intervals=('1h','4h','1d','1w'))
        self.assertEqual(report['coverage']['timeframe_assessments'],4)
        self.assertEqual({row['interval'] for row in report['results']},{'1h','4h','1d','1w'})
        self.assertEqual(sum('/spot/currency_pairs/' in url for url in calls),1)
        self.assertEqual(len(calls),7)
        self.assertFalse(report['buy_authorized'])

    def test_early_and_confirmed_taxonomy_derive_from_replayed_prices(self):
        fetch,_=source_factory()
        row=run([PAIR],'4h',fetch=fetch,now=NOW)['results'][0]
        self.assertEqual(row['research']['technical_classification'],'EARLY REVERSAL WATCH')
        raw=next(e['raw'] for e in row['provider_evidence'] if '/candlesticks?' in e['url'])
        raw[-1][2]='110';raw[-1][3]='111';raw[-1][4]='100';raw[-1][5]='102';raw[-1][1]='2000'
        candles=gate_candles(raw,interval_seconds=14400,now=NOW)
        computed=analyze('BCH/USDT',candles,source='fixture',observed_at=iso(NOW),interval='4h')
        self.assertEqual(computed['technical_classification'],'CONFIRMED TECHNICAL REVERSAL')
        self.assertFalse(computed['buy_authorized'])
        self.assertTrue(computed['metrics']['higher_low'])
        self.assertTrue(computed['metrics']['breakout'])
        plan=computed['conditional_plan']
        self.assertEqual(plan['gross_risk_reward'],2)
        self.assertAlmostEqual(plan['hypothetical_2r_target'],
            plan['entry_reference']+2*(plan['entry_reference']-plan['invalidation_reference']))
        self.assertEqual(plan['execution_status'],'NOT_EXECUTABLE_NOT_APPROVED')

    def test_intraday_does_not_enroll_unvalidated_paper_policy(self):
        fetch,_=source_factory()
        report=collect(fetch=fetch,now=NOW,intervals=('1h','4h'))
        state={'version':1,'accounts':{}}
        updated,result=strategy_lab.attach(report,state,strategy_lab.policy(),NOW)
        self.assertEqual(updated,state)
        self.assertEqual([r['status'] for r in result['rows']],['NOT_EVALUATED']*2)
        self.assertFalse(result['portfolio_evaluations'])

    def invalidation_state(self,midpoint=70):
        receipt={'delivered_at':iso(NOW-3600),'interval':'4h','entry_trigger':110,'invalidation':80}
        def fetch(url):
            if '/currency_pairs/' in url:
                return dict(id=PAIR,base='BCH',quote='USDT',type='normal',trade_status='tradable',st_tag=False)
            return dict(current=NOW*1000,update=NOW*1000,asks=[[str(midpoint+.1),'100']],bids=[[str(midpoint-.1),'100']])
        state={'version':1,'hypotheses':{}}
        followup.collect({PAIR:receipt},state,fetch,NOW,[PAIR])
        return state

    def test_invalidation_delivered_once_and_never_claims_fill(self):
        state=self.invalidation_state();sent=[];saved=[]
        summary=followup.deliver_invalidations(state,lambda t:sent.append(t) or True,lambda s:saved.append(copy.deepcopy(s)),now=NOW,allowed=[PAIR])
        self.assertEqual(summary['delivered'],1)
        self.assertTrue(sent[0].startswith('INVALIDATED SETUP\n'))
        self.assertIn('No stop fill',sent[0])
        self.assertFalse(summary['buy_authorized'])
        again=followup.deliver_invalidations(state,lambda _:self.fail('Duplicate'),lambda _:None,now=NOW,allowed=[PAIR])
        self.assertEqual(again['delivered'],0)
        self.assertEqual(saved[-1],state)

    def test_failed_or_stale_invalidation_never_advances_delivery(self):
        state=self.invalidation_state();old=copy.deepcopy(state)
        summary=followup.deliver_invalidations(state,lambda _:False,lambda _:self.fail('Unconfirmed state'),now=NOW,allowed=[PAIR])
        self.assertEqual(summary['failed'],1);self.assertEqual(state,old)
        summary=followup.deliver_invalidations(state,lambda _:self.fail('Stale send'),lambda _:None,now=NOW+901,allowed=[PAIR])
        self.assertEqual(summary['stale'],1)

    def test_invalidation_persistence_failure_surfaces(self):
        state=self.invalidation_state()
        def broken(_):
            raise OSError('State unavailable')
        with self.assertRaisesRegex(OSError, 'State unavailable'):
            followup.deliver_invalidations(state,lambda _:True,broken,now=NOW,allowed=[PAIR])

    def test_forged_breach_flag_and_modified_book_fail_closed(self):
        state=self.invalidation_state(midpoint=100)
        sample=next(iter(state['hypotheses'].values()))['samples'][-1]
        sample['at_or_below_invalidation_observed']=True
        summary=followup.deliver_invalidations(state,lambda _:self.fail('Forged flag'),lambda _:None,now=NOW,allowed=[PAIR])
        self.assertEqual(summary['delivered'],0)
        sample['raw_book']['bids']=[['70','100']]
        summary=followup.deliver_invalidations(state,lambda _:self.fail('Tampered book'),lambda _:self.fail('No state advancement'),now=NOW,allowed=[PAIR])
        self.assertEqual(summary['delivered'],0)
        self.assertEqual(list(summary['errors'].values()),['ValueError'])
