import copy
import unittest

import strategy_lab as lab
from pipeline_health import summarize


def candles(n=300):
    # Flat series gives a deterministic no-signal control.
    return [dict(timestamp=1700006400+i*86400,open=100.,high=101.,low=99.,
                 close=100.,volume=1_000_000.,closed=True) for i in range(n)]


def pending(a, entry=100., stop=95., target=110.):
    lab.queue(a,dict(entry=entry,stop=stop,target=target,signal_at=1),1)


def bar(at=2,o=101.,high=105.,low=100.,close=103.,volume=1_000_000.):
    return dict(timestamp=at,open=o,high=high,low=low,close=close,volume=volume,closed=True)


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.p=lab.policy();self.a=lab.account(self.p)

    def test_policy_is_research_only(self):
        self.assertFalse(self.p['buy_authorized']);self.assertFalse(self.p['orders_allowed'])

    def test_no_signal_fill_on_signal_bar(self):
        pending(self.a)
        self.assertIsNone(self.a['position']);self.assertEqual(self.a['trades'],[])

    def test_gap_entry_reconciles_risk_and_costs(self):
        pending(self.a,target=120.)
        lab.step(self.a,bar(o=108.,high=110.,low=107.,close=109.),self.p)
        pos=self.a['position']
        self.assertGreater(pos['entry'],108.)
        self.assertLessEqual(pos['quantity']*pos['entry'],100.)
        self.assertLess(self.a['equity'],1000.)

    def test_ambiguous_entry_stop_uses_adverse_fill_path(self):
        pending(self.a)
        lab.step(self.a,bar(high=115.,low=94.),self.p)
        self.assertIsNone(self.a['position'])
        self.assertLess(self.a['trades'][0]['net_pnl_usdt'],0)
        self.assertIn('STOP',self.a['trades'][0]['reason'])

    def test_invalidation_without_trigger_cancels(self):
        pending(self.a,entry=110.,target=120.)
        lab.step(self.a,bar(o=100.,high=105.,low=94.),self.p)
        self.assertIsNone(self.a['position'])
        self.assertEqual(self.a['trades'],[])
        self.assertEqual(self.a['events'][-1]['kind'],'CANCELLED')

    def test_gap_open_above_entry_cannot_avoid_samebar_stop_loss(self):
        pending(self.a,target=120.)
        lab.step(self.a,bar(o=101.,high=105.,low=94.),self.p)
        self.assertLess(self.a['trades'][0]['net_pnl_usdt'],0)

    def test_expiry(self):
        pending(self.a,entry=110.,target=120.)
        for i in range(4):
            lab.step(self.a,bar(at=i+2),self.p)
        self.assertIsNone(self.a['pending'])
        self.assertEqual(self.a['events'][-1]['kind'],'EXPIRED')

    def test_partial_fill_and_cancel_remainder(self):
        pending(self.a)
        lab.step(self.a,bar(volume=1000.),self.p)
        self.assertEqual(self.a['events'][-1]['kind'],'PARTIALLY_FILLED')
        self.assertLess(self.a['position']['quantity'],.01)
        self.assertIsNone(self.a['pending'])

    def test_no_capacity_no_fill(self):
        pending(self.a)
        lab.step(self.a,bar(volume=0.),self.p)
        self.assertIsNone(self.a['position'])

    def test_prospective_order_cannot_fill_before_observation(self):
        candidate=dict(entry=100.,stop=95.,target=110.,signal_at=1)
        lab.queue(self.a,candidate,150,eligible_after=150)
        lab.step(self.a,bar(at=100),self.p)
        self.assertIsNone(self.a['position'])
        self.assertEqual(self.a['pending']['age'],0)
        lab.step(self.a,bar(at=200),self.p)
        self.assertIsNotNone(self.a['position'])

    def test_same_bar_target_is_not_awarded(self):
        pending(self.a)
        lab.step(self.a,bar(high=115.,low=100.),self.p)
        self.assertIsNotNone(self.a['position']);self.assertEqual(self.a['trades'],[])

    def test_stop_first_and_gap_loss(self):
        pending(self.a)
        lab.step(self.a,bar(),self.p)
        lab.step(self.a,bar(at=3,o=90.,high=120.,low=85.,close=110.),self.p)
        trade=self.a['trades'][0]
        self.assertLess(trade['exit'],90.)
        self.assertLess(trade['net_pnl_usdt'],0)
        self.assertIn('STOP',trade['reason'])
        self.assertAlmostEqual(self.a['equity'],1000.+trade['net_pnl_usdt'])

    def test_target_after_entry_and_fees(self):
        pending(self.a)
        lab.step(self.a,bar(),self.p)
        lab.step(self.a,bar(at=3,o=108.,high=111.,low=105.,close=110.),self.p)
        self.assertEqual(self.a['trades'][0]['reason'],'TARGET')
        self.assertLess(self.a['trades'][0]['exit'],110.)
        self.assertGreater(self.a['trades'][0]['net_pnl_usdt'],0)

    def test_holding_expiry(self):
        pending(self.a,target=120.)
        for i in range(10):lab.step(self.a,bar(at=i+2),self.p)
        self.assertIsNone(self.a['position'])
        self.assertEqual(self.a['trades'][0]['reason'],'TIME_EXPIRY')

    def test_event_mutation_detected(self):
        pending(self.a);lab.verify_events(self.a['events'])
        self.a['events'][0]['at']=999
        with self.assertRaises(ValueError):lab.verify_events(self.a['events'])

    def test_closed_and_contiguous_required(self):
        c=candles();c[8]['timestamp']+=1
        with self.assertRaises(ValueError):lab.candles_valid(c,86400)
        c=candles();c[-1]['closed']=False
        with self.assertRaises(ValueError):lab.candles_valid(c,86400)

    def test_boolean_and_nonfinite_rejected(self):
        for value in (True,float('nan'),float('inf'),-1):
            c=candles();c[0]['volume']=value
            with self.assertRaises(ValueError):lab.candles_valid(c,86400)

    def test_split_embargo_and_no_false_validation(self):
        r=lab.evaluate('AVAX_USDT','1d',candles(),self.p)
        self.assertEqual(r['status'],'RESEARCH_ONLY')
        self.assertEqual(len(r['experiments']),3)
        for exp in r['experiments']:
            periods=exp['periods']
            self.assertGreater(periods['final_test']['start']-periods['validation']['end'],13*86400)
            self.assertEqual(exp['numerical_screen'],'INSUFFICIENT_EVIDENCE')
            self.assertTrue(exp['promotion'].startswith('BLOCKED'))
            self.assertEqual(periods['final_test']['metrics']['closed_trades'],0)

    def test_bootstrap_no_backdating_and_duplicate_noop(self):
        c=candles();at=c[-1]['timestamp']+86401
        state={'version':1,'accounts':{}}
        lab.prospective(state,'AVAX_USDT','1d',c,self.p,at)
        before=copy.deepcopy(state)
        lab.prospective(state,'AVAX_USDT','1d',c,self.p,at+1)
        self.assertEqual(state,before)
        for row in state['accounts'].values():
            self.assertEqual(row['monitoring_started_at'],at)
            self.assertEqual(row['account']['trades'],[])
            self.assertEqual(row['account']['events'][0]['kind'],'BOOTSTRAP')

    def test_revised_history_refused(self):
        c=candles();at=c[-1]['timestamp']+86401
        state={'version':1,'accounts':{}}
        lab.prospective(state,'AVAX_USDT','1d',c,self.p,at)
        c[-1]['volume']+=1
        with self.assertRaises(ValueError):lab.prospective(state,'AVAX_USDT','1d',c,self.p,at)

    def test_causal_replay_ignores_future_for_prior_events(self):
        # Process shared prefix twice; later extreme candles cannot change it.
        c=candles();modified=copy.deepcopy(c)
        modified[-1].update(open=1000.,close=1000.,high=1001.,low=999.)
        a,b=lab.account(self.p),lab.account(self.p)
        for history,acct in ((c,a),(modified,b)):
            for i in range(55,200):
                lab.step(acct,history[i],self.p)
                lab.queue(acct,lab.plan('AVAX_USDT','range_breakout',history[:i+1],self.p),history[i]['timestamp'])
        self.assertEqual(a,b)

    def test_new_bar_advances_once(self):
        c=candles();state={'version':1,'accounts':{}}
        lab.prospective(state,'AVAX_USDT','1d',c,self.p,c[-1]['timestamp']+86401)
        c=candles(301)
        lab.prospective(state,'AVAX_USDT','1d',c,self.p,c[-1]['timestamp']+86401)
        self.assertTrue(all(r['account']['bars']==1 for r in state['accounts'].values()))


class HealthTests(unittest.TestCase):
    def test_continued_failure_cannot_look_complete(self):
        reports={k:{} for k in ('scan','reversal','technical_followup','strategy_lab')}
        r=summarize({'scan':'success','reversal':'failure'},reports)
        self.assertEqual(r['status'],'DEGRADED')
        self.assertEqual(r['overall_objective'],'BLOCKED')

    def test_missing_artifact_degrades(self):
        self.assertEqual(summarize({'scan':'success'}, {})['status'],'DEGRADED')
